import type { Config } from "@netlify/functions";
import { Document, Packer, Paragraph, TextRun, AlignmentType, TabStopType, TabStopLeader } from "docx";
import mammoth from "mammoth";
import Busboy from "busboy";

// ── helpers ──────────────────────────────────────────────────────────────────

function toProperCase(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

function stripBulletsAndSymbols(text: string): string {
  return text.replace(/^[\s\-•\*►▪▶◆◇→⇒✓✔✗✘·]+/gm, "").replace(/\r/g, "");
}

function removeUrlsAndHyperlinks(text: string): string {
  return text.replace(/https?:\/\/[^\s]+/g, "").replace(/www\.[^\s]+/g, "");
}

// ── parse multipart form ─────────────────────────────────────────────────────

async function parseMultipart(
  req: Request
): Promise<{ fileBuffer: Buffer; fileType: string }> {
  return new Promise((resolve, reject) => {
    const contentType = req.headers.get("content-type") || "";
    const busboy = Busboy({ headers: { "content-type": contentType } });
    let fileBuffer: Buffer | null = null;
    let fileType = "";

    busboy.on("file", (_field, stream, info) => {
      fileType = info.mimeType;
      const chunks: Buffer[] = [];
      stream.on("data", (d: Buffer) => chunks.push(d));
      stream.on("end", () => {
        fileBuffer = Buffer.concat(chunks);
      });
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

// ── extract text from various file types ─────────────────────────────────────

async function extractText(
  fileBuffer: Buffer,
  mimeType: string,
  filename: string
): Promise<string> {
  const ext = filename.split(".").pop()?.toLowerCase() || "";

  // DOCX
  if (
    mimeType.includes("wordprocessingml") ||
    mimeType.includes("msword") ||
    ext === "docx" ||
    ext === "doc"
  ) {
    const result = await mammoth.extractRawText({ buffer: fileBuffer });
    return result.value;
  }

  // Plain text / RTF / ODT
  if (
    mimeType.startsWith("text/") ||
    ext === "txt" ||
    ext === "rtf" ||
    ext === "odt"
  ) {
    return fileBuffer.toString("utf-8");
  }

  // PDF – use base64 and send to Claude for extraction
  if (mimeType === "application/pdf" || ext === "pdf") {
    return "[PDF_BASE64]" + fileBuffer.toString("base64");
  }

  // Fallback: treat as text
  return fileBuffer.toString("utf-8");
}

// ── call Claude AI ────────────────────────────────────────────────────────────

async function parseWithClaude(
  rawText: string,
  isPdf: boolean,
  pdfBase64?: string
): Promise<ResumeData> {
  const apiKey = Netlify.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY not configured");

  const systemPrompt = `You are a resume parser. Extract structured data from the provided resume text.

Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{
  "firstName": "string",
  "lastName": "string",
  "summary": ["bullet point 1", "bullet point 2", ...],
  "technicalSkills": ["line 1", "line 2", ...],
  "education": ["entry 1", "entry 2", ...],
  "certifications": ["entry 1", ...],
  "training": ["entry 1", ...],
  "experience": [
    {
      "company": "Company Name",
      "location": "City, State",
      "duration": "Month Year – Month Year",
      "role": "Job Title",
      "descriptions": ["bullet 1", "bullet 2", ...]
    }
  ]
}

Rules:
- Extract candidate full name for firstName and lastName
- Summary: each distinct point as a separate array item (preserve original wording exactly)
- Technical Skills: each distinct skill line as a separate item (preserve original wording exactly)
- Education: each degree/institution as a separate item (preserve original wording exactly, no URLs)
- Certifications: each cert as a separate item (preserve original wording exactly, no URLs)
- Training: each training as a separate item (preserve original wording exactly, no URLs)
- Experience: for each position, extract company, location, duration, role, and description bullets
- Preserve exact original wording - do NOT rephrase, summarize or alter any text
- Remove any URLs, hyperlinks, or web addresses from all fields
- Remove any bullet symbols from the text (•, -, *, etc.) - just return clean text
- If a section is missing, use an empty array []`;

  let messages: object[];

  if (isPdf && pdfBase64) {
    messages = [
      {
        role: "user",
        content: [
          {
            type: "document",
            source: {
              type: "base64",
              media_type: "application/pdf",
              data: pdfBase64,
            },
          },
          {
            type: "text",
            text: "Parse this resume and return the structured JSON as instructed.",
          },
        ],
      },
    ];
  } else {
    messages = [
      {
        role: "user",
        content: `Parse this resume and return the structured JSON as instructed:\n\n${rawText}`,
      },
    ];
  }

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 4096,
      system: systemPrompt,
      messages,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Claude API error: ${err}`);
  }

  const data = await response.json();
  const text = data.content
    .filter((b: { type: string }) => b.type === "text")
    .map((b: { text: string }) => b.text)
    .join("");

  // Strip any markdown code fences if present
  const clean = text.replace(/```json\s*/g, "").replace(/```\s*/g, "").trim();
  return JSON.parse(clean) as ResumeData;
}

// ── types ─────────────────────────────────────────────────────────────────────

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

// ── build docx ────────────────────────────────────────────────────────────────

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
  const prefix = indent ? "  • " : "• ";
  return new Paragraph({
    children: [
      new TextRun({
        text: prefix + cleanText,
        font: TNR,
        size: 20,
      }),
    ],
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

  // ── Candidate Name ──
  const fullName = toProperCase(`${data.firstName} ${data.lastName}`);
  paragraphs.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ text: fullName, font: TNR, size: 22, bold: true }),
      ],
      spacing: { before: 0, after: 0, line: 240 },
    })
  );

  // ── Summary ──
  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Summary"));
  for (const point of data.summary) {
    paragraphs.push(bulletParagraph(point, false));
  }

  // ── Technical Skills ──
  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Technical Skills"));
  for (const skill of data.technicalSkills) {
    paragraphs.push(plainParagraph(skill));
  }

  // ── Education, Certification & Training ──
  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Education, Certification & Training"));

  const allECT = [
    ...data.education,
    ...data.certifications,
    ...data.training,
  ];
  for (const entry of allECT) {
    paragraphs.push(bulletParagraph(entry, true));
  }

  // ── Professional Experience ──
  paragraphs.push(emptyLine());
  paragraphs.push(sectionHeading("Professional Experience"));

  for (let i = 0; i < data.experience.length; i++) {
    const exp = data.experience[i];
    const companyLocation = `${exp.company}, ${exp.location}`;

    // Company, Location [TAB] Duration
    paragraphs.push(
      new Paragraph({
        children: [
          new TextRun({
            text: companyLocation,
            font: TNR,
            size: 20,
          }),
          new TextRun({
            text: "\t" + (exp.duration || ""),
            font: TNR,
            size: 20,
          }),
        ],
        tabStops: [
          {
            type: TabStopType.RIGHT,
            position: 9360,
            leader: TabStopLeader.NONE,
          },
        ],
        spacing: { before: 0, after: 0, line: 240 },
      })
    );

    // Role
    paragraphs.push(
      new Paragraph({
        children: [
          new TextRun({ text: exp.role, font: TNR, size: 20 }),
        ],
        spacing: { before: 0, after: 0, line: 240 },
      })
    );

    // Descriptions
    for (const desc of exp.descriptions) {
      paragraphs.push(bulletParagraph(desc, true));
    }

    // Space after each project (except last)
    if (i < data.experience.length - 1) {
      paragraphs.push(emptyLine());
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: paragraphs,
      },
    ],
  });

  return await Packer.toBuffer(doc);
}

// ── main handler ──────────────────────────────────────────────────────────────

export default async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const contentType = req.headers.get("content-type") || "";

    if (!contentType.includes("multipart/form-data")) {
      return new Response(
        JSON.stringify({ error: "Expected multipart/form-data" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    // Parse the uploaded file
    const { fileBuffer, fileType } = await parseMultipart(req);

    // Get filename from content-disposition or default
    const filename =
      req.headers.get("x-filename") || `resume.${fileType.split("/")[1] || "bin"}`;

    // Extract text
    const rawText = await extractText(fileBuffer, fileType, filename);

    const isPdf = rawText.startsWith("[PDF_BASE64]");
    const pdfBase64 = isPdf ? rawText.slice("[PDF_BASE64]".length) : undefined;
    const textForParsing = isPdf ? "" : rawText;

    // Parse with Claude AI
    const resumeData = await parseWithClaude(textForParsing, isPdf, pdfBase64);

    // Build the formatted DOCX
    const docxBuffer = await buildDocx(resumeData);

    // Construct filename: FirstName LastName.docx
    const safeFirst = toProperCase(resumeData.firstName).replace(/\s+/g, "");
    const safeLast = toProperCase(resumeData.lastName).replace(/\s+/g, "");
    const outputFilename = `${safeFirst} ${safeLast}.docx`;

    return new Response(docxBuffer, {
      status: 200,
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename="${outputFilename}"`,
        "X-Candidate-Name": `${resumeData.firstName} ${resumeData.lastName}`,
      },
    });
  } catch (err: unknown) {
    console.error("Error processing resume:", err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
};

export const config: Config = {
  path: "/api/format-resume",
};
