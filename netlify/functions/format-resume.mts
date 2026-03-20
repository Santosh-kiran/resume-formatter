import type { Config } from "@netlify/functions";
import { Document, Packer, Paragraph, TextRun, AlignmentType, TabStopType, TabStopLeader } from "docx";
import mammoth from "mammoth";
import Busboy from "busboy";

function toProperCase(name: string): string {
  return name.trim().split(/\s+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}

function stripBulletsAndSymbols(text: string): string {
  return text.replace(/^[\s\-•\*►▪▶◆◇→⇒✓✔✗✘·]+/gm, "").replace(/\r/g, "");
}

function removeUrlsAndHyperlinks(text: string): string {
  return text.replace(/https?:\/\/[^\s]+/g, "").replace(/www\.[^\s]+/g, "");
}

async function parseMultipart(req: Request): Promise<{ fileBuffer: Buffer; fileType: string }> {
  return new Promise((resolve, reject) => {
    const contentType = req.headers.get("content-type") || "";
    const busboy = Busboy({ headers: { "content-type": contentType } });
    let fileBuffer: Buffer | null = null;
    let fileType = "";
    busboy.on("file", (_field, stream, info) => {
      fileType = info.mimeType;
      const chunks: Buffer[] = [];
      stream.on("data", (d: Buffer) => chunks.push(d));
      stream.on("end", () => { fileBuffer = Buffer.concat(chunks); });
    });
    busboy.on("finish", () => {
      if (fileBuffer) resolve({ fileBuffer, fileType });
      else reject(new Error("No file found in upload"));
    });
    busboy.on("error", reject);
    req.arrayBuffer().then((ab) => {
      const buf = Buffer.from(ab);
      busboy.write(buf);
      busboy.end();
    });
  });
}

async function extractText(fileBuffer: Buffer, mimeType: string, filename: string): Promise<string> {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (mimeType.includes("wordprocessingml") || mimeType.includes("msword") || ext === "docx" || ext === "doc") {
    const result = await mammoth.extractRawText({ buffer: fileBuffer });
    return result.value;
  }
  if (mimeType.startsWith("text/") || ext === "txt" || ext === "rtf" || ext === "odt") {
    return fileBuffer.toString("utf-8");
  }
  if (mimeType === "application/pdf" || ext === "pdf") {
    return "[PDF_BASE64]" + fileBuffer.toString("base64");
  }
  return fileBuffer.toString("utf-8");
}

interface ExperienceEntry {
  company: string;
  location: string;
  duration: string;
  role: string;
  descriptions: string[];
}

interface ResumeData {
  firstName: string;
  lastName: string;
  summary: string[];
  technicalSkills: string[];
  education: string[];
  certifications: string[];
  training: string[];
  experience: ExperienceEntry[];
}

async function parseWithOpenAI(rawText: string, isPdf: boolean, pdfBase64?: string): Promise<ResumeData> {
  const apiKey = Netlify.env.get("OPENAI_API_KEY");
  if (!apiKey) throw new Error("OPENAI_API_KEY not configured");

  const systemPrompt = `You are a resume parser. Extract structured data from the provided resume.
Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{
  "firstName": "string",
  "lastName": "string",
  "summary": ["point 1", "point 2"],
  "technicalSkills": ["line 1", "line 2"],
  "education": ["entry 1"],
  "certifications": ["entry 1"],
  "training": ["entry 1"],
  "experience": [
    {
      "company": "Company Name",
      "location": "City, State",
      "duration": "Month Year – Month Year",
      "role": "Job Title",
      "descriptions": ["bullet 1", "bullet 2"]
    }
  ]
}
Rules:
- Preserve exact original wording — do NOT rephrase or alter any text
- Remove all URLs, hyperlinks, and bullet symbols from all fields
- If a section is missing, use an empty array []`;

  let userContent: object;
  if (isPdf && pdfBase64) {
    userContent = [
      { type: "text", text: "Parse this resume PDF and return the structured JSON:" },
      { type: "image_url", image_url: { url: `data:image/jpeg;base64,${pdfBase64}`, detail: "high" } }
    ];
  } else {
    userContent = `Parse this resume and return the structured JSON:\n\n${rawText}`;
  }

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: "gpt-4o",
      max_tokens: 4096,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userContent }
      ]
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`OpenAI API error: ${err}`);
  }

  const data = await response.json();
  const text = data.choices?.[0]?.message?.content || "{}";
  return JSON.parse(text) as ResumeData;
}

const TNR = "Times New Roman";

function sectionHeading(text: string): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text, font: TNR, size: 20, bold: true })],
    spacing: { before: 0, after: 0, line: 240 },
  });
}

function emptyLine(): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text: "", font: TNR, size: 20 })],
    spacing: { before: 0, after: 0, line: 240 },
  });
}

function bulletParagraph(text: string, indent = false): Paragraph {
  const cleanText = stripBulletsAndSymbols(removeUrlsAndHyperlinks(text)).trim();
  const prefix = indent ? "  \u2022 " : "\u2022 ";
  return new Paragraph({
    children: [new TextRun({ text: prefix + cleanText, font: TNR, size: 20 })],
    spacing: { before: 0, after: 0, line: 240 },
  });
}

function plainParagraph(text: string): Paragraph {
  const cleanText = stripBulletsAndSymbols(removeUrlsAndHyperlinks(text)).trim();
  return new Paragraph({
    children: [new TextRun({ text: cleanText, font: TNR, size: 20 })],
    spacing: { before: 0, after: 0, line: 240 },
  });
}

async function buildDocx(data: ResumeData): Promise<Buffer> {
  const paragraphs: Paragraph[] = [];

  const fullName = toProperCase(`${data.firstName} ${data.lastName}`);
  paragraphs.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: fullName, font: TNR, size: 22, bold: true })],
    spacing: { before: 0, after: 0, line: 240 },
  }));

  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Summary"));
  for (const point of data.summary) paragraphs.push(bulletParagraph(point, false));

  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Technical Skills"));
  for (const skill of data.technicalSkills) paragraphs.push(plainParagraph(skill));

  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Education, Certification & Training"));
  for (const entry of [...data.education, ...data.certifications, ...data.training]) {
    paragraphs.push(bulletParagraph(entry, true));
  }

  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Professional Experience"));

  for (let i = 0; i < data.experience.length; i++) {
    const exp = data.experience[i];
    paragraphs.push(new Paragraph({
      children: [
        new TextRun({ text: `${exp.company}, ${exp.location}`, font: TNR, size: 20 }),
        new TextRun({ text: "\t" + (exp.duration || ""), font: TNR, size: 20 }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9360, leader: TabStopLeader.NONE }],
      spacing: { before: 0, after: 0, line: 240 },
    }));
    paragraphs.push(new Paragraph({
      children: [new TextRun({ text: exp.role, font: TNR, size: 20 })],
      spacing: { before: 0, after: 0, line: 240 },
    }));
    for (const desc of exp.descriptions) paragraphs.push(bulletParagraph(desc, true));
    if (i < data.experience.length - 1) paragraphs.push(emptyLine());
  }

  const doc = new Document({ sections: [{ properties: {}, children: paragraphs }] });
  return await Packer.toBuffer(doc);
}

export default async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204 });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405, headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const contentType = req.headers.get("content-type") || "";
    if (!contentType.includes("multipart/form-data")) {
      return new Response(JSON.stringify({ error: "Expected multipart/form-data" }), {
        status: 400, headers: { "Content-Type": "application/json" },
      });
    }

    const { fileBuffer, fileType } = await parseMultipart(req);
    const filename = req.headers.get("x-filename") || `resume.bin`;
    const rawText = await extractText(fileBuffer, fileType, filename);
    const isPdf = rawText.startsWith("[PDF_BASE64]");
    const pdfBase64 = isPdf ? rawText.slice("[PDF_BASE64]".length) : undefined;

    const resumeData = await parseWithOpenAI(isPdf ? "" : rawText, isPdf, pdfBase64);
    const docxBuffer = await buildDocx(resumeData);

    const safeFirst = toProperCase(resumeData.firstName).replace(/\s+/g, "");
    const safeLast = toProperCase(resumeData.lastName).replace(/\s+/g, "");
    const outputFilename = `${safeFirst} ${safeLast}.docx`;

    return new Response(docxBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename="${outputFilename}"`,
        "X-Candidate-Name": `${resumeData.firstName} ${resumeData.lastName}`,
      },
    });
  } catch (err: unknown) {
    console.error("Error:", err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return new Response(JSON.stringify({ error: message }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }
};

export const config: Config = { path: "/api/format-resume" };
