import { GoogleGenAI } from '@google/genai';

export interface FormAttachment {
  name?: string;
  mimeType: string;
  /** base64 encoded string */
  data: string;
}

/**
 * Isolated User Document Ingestion Service
 * 
 * Specifically designed for user-uploaded racecards, TAB Computaform,
 * tipping sheets, and steward reports.
 * 
 * Invariant: core_agent/skills/parsers/pdf_harvester.py remains untouched.
 */
export async function extractDocumentContent(
  attachment: FormAttachment,
  summarizeMode = false
): Promise<string> {
  const geminiApiKey = process.env.GEMINI_API_KEY;

  // If Gemini API Key is available, use Google AI Studio's multimodal engine
  // to convert the PDF or image into a high-fidelity Markdown table
  if (geminiApiKey) {
    try {
      const ai = new GoogleGenAI({ apiKey: geminiApiKey });
      const prompt = summarizeMode
        ? `You are a South African horse racing document specialist. Extract the contents of this racecard / PDF / report into an Executive Meeting Overview:
1. Track / Course, Surface, Rail Placement, Going, Weather (if stated)
2. Races List: Race Numbers, Times, Distances, Conditions
3. Runners Table: Draw, Horse Name, Weight (kg), Jockey, Trainer, Merit Rating (MR), Recent Form (last runs)
4. Any Notable Steward Notices, Scratches, or Track Changes.

Present clearly with markdown headers and clean tables. Do not invent fictitious odds.`
        : `You are an expert racing data extractor. Extract the text, tabular racecard data, and runner details from this document into clean, structured Markdown tables:
Columns: No | Draw | Horse | Mass (kg) | Jockey | Trainer | MR | Form | Remarks
Preserve exact names, numbers, and dates.`;

      const response = await ai.models.generateContent({
        model: 'gemini-3.1-flash-lite',
        contents: [
          {
            role: 'user',
            parts: [
              { text: prompt },
              {
                inlineData: {
                  mimeType: attachment.mimeType,
                  data: attachment.data,
                },
              },
            ],
          },
        ],
        config: {
          temperature: 0.2,
        },
      });

      const extracted = response.text?.trim();
      if (extracted) {
        return extracted;
      }
    } catch (err) {
      console.warn('[FormReaderService] Gemini fast-pass extraction failed, falling back:', err);
    }
  }

  // Fallback: If it's a PDF and no Gemini key, extract raw text strings from PDF stream
  if (attachment.mimeType === 'application/pdf') {
    try {
      const buffer = Buffer.from(attachment.data, 'base64');
      const rawStr = buffer.toString('binary');
      // Regex extraction for uncompressed or Flate text fragments in standard PDF streams
      const textMatches: string[] = [];
      const btEtRegex = /BT[\s\S]*?ET/g;
      let match;
      while ((match = btEtRegex.exec(rawStr)) !== null) {
        const tjMatches = match[0].match(/\((.*?)\)\s*T[jJ]/g);
        if (tjMatches) {
          const line = tjMatches.map(m => m.replace(/^[(]/, '').replace(/[)]\s*T[jJ]$/, '')).join(' ');
          if (line.trim().length > 2) {
            textMatches.push(line.trim());
          }
        }
      }
      if (textMatches.length > 0) {
        return `[Extracted PDF Content from ${attachment.name || 'document'}]:\n` + textMatches.slice(0, 150).join('\n');
      }
    } catch (fallbackErr) {
      console.warn('[FormReaderService] Fallback PDF text decode failed:', fallbackErr);
    }
  }

  return `[Attached file: ${attachment.name || 'Racecard / Form Document'} (${attachment.mimeType})]`;
}
