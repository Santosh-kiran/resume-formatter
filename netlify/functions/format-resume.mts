import type { Config } from "@netlify/functions";
import { Document, Packer, Paragraph, TextRun, AlignmentType, TabStopType } from "docx";
import mammoth from "mammoth";
import Busboy from "busboy";

function toProperCase(name: string): string {
  return name.trim().split(/\s+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}
function stripBullets(text: string): string {
  return text.replace(/^[\s\-•\*►▪▶◆◇→⇒✓✔✗✘·]+/gm, "").replace(/\r/g, "").trim();
}
function removeUrls(text: string): string {
  return text.replace(/https?:\/\/[^\s]+/g, "").replace(/www\.[^\s]+/g, "").trim();
}
function clean(text: string): string {
  return removeUrls(stripBullets(text)).trim();
}

async function parseMultipart(req: Request): Promise<{ fileBuffer: Buffer; fileType: string; filename: string }> {
  return new Promise((resolve, reject) => {
    const ct = req.headers.get("content-type") || "";
    const bb = Busboy({ headers: { "content-type": ct } });
    let buf: Buffer | null = null;
    let mime = "";
    let fname = "resume.docx";
    bb.on("file", (field, stream, info) => {
      mime = info.mimeType;
      fname = info.filename || fname;
      const chunks: Buffer[] = [];
      stream.on("data", (d: Buffer) => chunks.push(d));
      stream.on("end", () => { buf = Buffer.concat(chunks); });
    });
    bb.on("finish", () => buf ? resolve({ fileBuffer: buf, fileType: mime, filename: fname }) : reject(new Error("No file uploaded")));
    bb.on("error", reject);
    req.arrayBuffer().then(ab => { bb.write(Buffer.from(ab)); bb.end(); });
  });
}

async function extractText(buf: Buffer, mime: string, filename: string): Promise<string> {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (mime.includes("wordprocessingml") || mime.includes("msword") || ext === "docx" || ext === "doc") {
    const r = await mammoth.extractRawText({ buffer: buf });
    return r.value;
  }
  if (mime.startsWith("text/") || ["txt","rtf","odt"].includes(ext)) return buf.toString("utf-8");
  if (mime === "application/pdf" || ext === "pdf") return "__PDF__" + buf.toString("base64");
  return buf.toString("utf-8");
}

interface Exp { company: string; location: string; duration: string; role: string; descriptions: string[]; }
interface ResumeData { firstName: string; lastName: string; summary: string[]; technicalSkills: string[]; education: string[]; certifications: string[]; training: string[]; experience: Exp[]; }

async function callOpenAI(text: string, isPdf: boolean, pdfB64?: string): Promise<ResumeData> {
  const key = Netlify.env.get("OPENAI_API_KEY");
  if (!key) throw new Error("OPENAI_API_KEY not set in environment variables");

  const sys = `You are a resume parser. Return ONLY a JSON object, no markdown, no explanation.
JSON structure:
{"firstName":"","lastName":"","summary":[],"technicalSkills":[],"education":[],"certifications":[],"training":[],"experience":[{"company":"","location":"","duration":"","role":"","descriptions":[]}]}
Rules:
- Preserve exact original wording, do not rephrase anything
- Remove all bullet symbols, URLs, hyperlinks from text values
- education = degrees only, certifications = certs only, training = training only
- If section missing use empty array []`;

  const userMsg: object = isPdf && pdfB64
    ? [{ type: "text", text: "Parse this resume PDF:" }, { type: "image_url", image_url: { url: `data:image/png;base64,${pdfB64}`, detail: "high" } }]
    : `Parse this resume:\n\n${text.slice(0, 12000)}`;

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${key}` },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      max_tokens: 3000,
      response_format: { type: "json_object" },
      messages: [{ role: "system", content: sys }, { role: "user", content: userMsg }]
    })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`OpenAI error ${res.status}: ${err.slice(0, 300)}`);
  }
  const data = await res.json();
  const raw = data.choices?.[0]?.message?.content || "{}";
  return JSON.parse(raw) as ResumeData;
}

const F = "Times New Roman";
const sp = { before: 0, after: 0, line: 240 };

function heading(t: string) {
  return new Paragraph({ children: [new TextRun({ text: t, font: F, size: 20, bold: true })], spacing: sp });
}
function blank() {
  return new Paragraph({ children: [new TextRun({ text: "", font: F, size: 20 })], spacing: sp });
}
function bullet(t: string, indent = false) {
  return new Paragraph({ children: [new TextRun({ text: (indent ? "  \u2022 " : "\u2022 ") + clean(t), font: F, size: 20 })], spacing: sp });
}
function plain(t: string) {
  return new Paragraph({ children: [new TextRun({ text: clean(t), font: F, size: 20 })], spacing: sp });
}
function expHeader(company: string, location: string, duration: string) {
  return new Paragraph({
    children: [
      new TextRun({ text: `${company}, ${location}`, font: F, size: 20 }),
      new TextRun({ text: "\t" + duration, font: F, size: 20 }),
    ],
    tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
    spacing: sp,
  });
}

async function buildDoc(d: ResumeData): Promise<Buffer> {
  const ps: Paragraph[] = [];

  // Name
  ps.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: toProperCase(`${d.firstName} ${d.lastName}`), font: F, size: 22, bold: true })],
    spacing: sp,
  }));

  // Summary
  ps.push(blank()); ps.push(heading("Summary"));
  (d.summary || []).forEach(x => ps.push(bullet(x)));

  // Technical Skills
  ps.push(blank()); ps.push(heading("Technical Skills"));
  (d.technicalSkills || []).forEach(x => ps.push(plain(x)));

  // Education, Certification & Training
  ps.push(blank()); ps.push(heading("Education, Certification & Training"));
  [...(d.education||[]),...(d.certifications||[]),...(d.training||[])].forEach(x => ps.push(bullet(x, true)));

  // Professional Experience
  ps.push(blank()); ps.push(heading("Professional Experience"));
  (d.experience || []).forEach((e, i) => {
    ps.push(expHeader(e.company || "", e.location || "", e.duration || ""));
    ps.push(plain(e.role || ""));
    (e.descriptions || []).forEach(x => ps.push(bullet(x, true)));
    if (i < (d.experience.length - 1)) ps.push(blank());
  });

  return await Packer.toBuffer(new Document({ sections: [{ properties: {}, children: ps }] }));
}

export default async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST only" }), { status: 405, headers: { "Content-Type": "application/json" } });
  }
  try {
    const { fileBuffer, fileType, filename } = await parseMultipart(req);
    const xfn = req.headers.get("x-filename") || filename;
    const raw = await extractText(fileBuffer, fileType, xfn);
    const isPdf = raw.startsWith("__PDF__");
    const resume = await callOpenAI(isPdf ? "" : raw, isPdf, isPdf ? raw.slice(7) : undefined);
    const docBuf = await buildDoc(resume);
    const fn = toProperCase(resume.firstName || "").replace(/\s+/g,"");
    const ln = toProperCase(resume.lastName || "").replace(/\s+/g,"");
    const outName = `${fn} ${ln}.docx`;
    return new Response(docBuf, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename="${outName}"`,
        "X-Candidate-Name": `${resume.firstName} ${resume.lastName}`,
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("RESUME ERROR:", msg);
    return new Response(JSON.stringify({ error: msg }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
};

export const config: Config = { path: "/api/format-resume" };
