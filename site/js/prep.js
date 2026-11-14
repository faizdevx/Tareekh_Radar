// Hearing preparation content and parsers (pure; no DOM).
// Checklists are general reminders, not legal requirements: the person is always told to confirm with their lawyer.
import { decodePurpose } from "./help.js";

const I = (id, en, hi) => ({ id, en, hi });

/** What to carry on any hearing day, plus extras by stage group (from the stage decoder). */
export const CARRY = {
  any: [I("id_proof", "Photo ID (Aadhaar, voter ID, etc.)", "फ़ोटो पहचान पत्र (आधार, वोटर आईडी आदि)"),
    I("papers", "Your copy of the case papers", "मामले के कागज़ों की अपनी प्रति"),
    I("last_order", "The last order sheet (or a photo of it)", "आख़िरी आदेश-पत्र (या उसकी फ़ोटो)"),
    I("lawyer_no", "Your lawyer's phone number", "अपने वकील का फ़ोन नंबर")],
  service: [I("addresses", "Correct current address of the other side", "दूसरे पक्ष का सही वर्तमान पता"),
    I("pf_receipt", "Receipt of process fee paid, if any", "जमा की गई प्रोसेस फ़ीस की रसीद, यदि हो")],
  reply: [I("reply_copy", "Copy of the reply / written statement filed", "दाख़िल जवाब / लिखित कथन की प्रति")],
  issues: [I("pleadings", "Copies of the plaint/complaint and reply", "वादपत्र/शिकायत और जवाब की प्रतियाँ")],
  evidence: [I("originals", "Originals of documents you rely on (to be shown in court)", "जिन दस्तावेज़ों पर आप निर्भर हैं उनके मूल (अदालत में दिखाने के लिए)"),
    I("witness", "Your witnesses, or confirm with your lawyer that they were summoned", "अपने गवाह, या वकील से पुष्टि कि उन्हें समन गया")],
  arguments: [I("notes", "Your short notes of key facts and dates", "मुख्य तथ्यों और तारीखों के अपने छोटे नोट्स")],
  judgment: [I("copy_app", "Money/stamps for a certified copy application", "प्रमाणित प्रति आवेदन के लिए पैसे/स्टांप")],
  execution: [I("decree_copy", "Certified copy of the decree/order", "डिक्री/आदेश की प्रमाणित प्रति"),
    I("property_info", "Details of the other side's property, bank or salary", "दूसरे पक्ष की संपत्ति, बैंक या वेतन का विवरण")],
  filing: [],
};

/** Documents commonly needed for each case type (tick once you have them). */
export const DOCS = {
  cheque_bounce: [I("cheque", "Original cheque", "मूल चेक"), I("return_memo", "Bank return memo", "बैंक का रिटर्न मेमो"),
    I("notice_copy", "Copy of the legal demand notice", "कानूनी माँग नोटिस की प्रति"), I("notice_proof", "Postal receipt and delivery proof of the notice", "नोटिस की डाक रसीद और पहुँचने का सबूत"),
    I("debt_proof", "Proof of the debt (agreement, invoices, messages)", "कर्ज़ का सबूत (अनुबंध, बिल, संदेश)")],
  maintenance: [I("marriage_proof", "Proof of marriage", "विवाह का सबूत"), I("child_docs", "Children's birth certificates", "बच्चों के जन्म प्रमाणपत्र"),
    I("expenses_list", "List of your monthly expenses", "आपके मासिक ख़र्च की सूची"), I("income_info", "Any information about the other side's income", "दूसरे पक्ष की आय की कोई जानकारी"),
    I("prev_orders", "Copies of any earlier orders", "पहले के किसी भी आदेश की प्रतियाँ")],
  matrimonial: [I("marriage_proof", "Proof of marriage (certificate, photos, invitation card)", "विवाह का सबूत (प्रमाणपत्र, फ़ोटो, निमंत्रण पत्र)"),
    I("address_proof", "Address proofs", "पते के सबूत"), I("child_docs", "Children's documents", "बच्चों के दस्तावेज़"), I("prev_orders", "Copies of earlier complaints or orders", "पहले की शिकायतों या आदेशों की प्रतियाँ")],
  motor_accident: [I("fir", "FIR copy", "एफ़आईआर की प्रति"), I("medical", "Medical records and bills", "मेडिकल रिकॉर्ड और बिल"),
    I("disability", "Disability certificate, if any", "विकलांगता प्रमाणपत्र, यदि हो"), I("income_proof", "Income proof of the injured/deceased", "घायल/मृतक की आय का सबूत"),
    I("vehicle_ins", "Vehicle and insurance details of the other vehicle", "दूसरे वाहन और उसके बीमा का विवरण"), I("heir_proof", "Death certificate and legal heir proof (fatal cases)", "मृत्यु प्रमाणपत्र और कानूनी वारिस का सबूत (मृत्यु के मामलों में)")],
  civil_suit: [I("title_docs", "Title/ownership documents", "स्वामित्व के दस्तावेज़"), I("revenue", "Revenue records (e.g. khatauni, jamabandi)", "राजस्व रिकॉर्ड (जैसे खतौनी, जमाबंदी)"),
    I("agreements", "Agreements and payment proofs", "अनुबंध और भुगतान के सबूत"), I("letters", "Letters, notices and messages exchanged", "आपस में भेजे पत्र, नोटिस और संदेश")],
  criminal_case: [I("fir", "FIR copy", "एफ़आईआर की प्रति"), I("chargesheet", "Copy of the chargesheet, if supplied", "आरोप-पत्र की प्रति, यदि मिली हो"),
    I("bail_order", "Bail order copy", "ज़मानत आदेश की प्रति"), I("surety", "Surety's documents", "ज़मानतदार के दस्तावेज़")],
  bail: [I("fir", "FIR copy", "एफ़आईआर की प्रति"), I("custody", "Date of arrest / custody details", "गिरफ़्तारी की तारीख / हिरासत का विवरण"),
    I("surety", "Surety's ID and property/solvency proof", "ज़मानतदार का पहचान पत्र और संपत्ति/हैसियत का सबूत"), I("prev_bail", "Any earlier bail orders", "पहले के कोई ज़मानत आदेश")],
  execution: [I("decree_copy", "Certified copy of the decree", "डिक्री की प्रमाणित प्रति"), I("property_info", "Details of the other side's property, bank or salary", "दूसरे पक्ष की संपत्ति, बैंक या वेतन का विवरण")],
  appeal_revision: [I("judgment_copy", "Certified copy of the judgment/order challenged", "चुनौती दिए गए फ़ैसले/आदेश की प्रमाणित प्रति"), I("lower_papers", "Lower court papers", "निचली अदालत के कागज़")],
  land_acquisition: [I("award_copy", "Copy of the land acquisition award", "भूमि अधिग्रहण अवार्ड की प्रति"), I("revenue", "Revenue records", "राजस्व रिकॉर्ड"), I("sale_deeds", "Sale deeds of nearby land (for value)", "आसपास की ज़मीन के बैनामे (मूल्य के लिए)")],
  other: [],
};

/** Settlement routes by case type: often listed for National Lok Adalats, sometimes, or not usually. */
export const SETTLE = {
  cheque_bounce: "often", motor_accident: "often", civil_suit: "often", execution: "some", land_acquisition: "some",
  maintenance: "some", matrimonial: "some", criminal_case: "compoundable", appeal_revision: "some", bail: "no", other: "some",
};

/** National Lok Adalat dates from NALSA letter L/34/2018-NALSA (04.12.2025). States sometimes reschedule:
 * always tell people to confirm with their DLSA. Add next year's dates when NALSA publishes them. */
export const LOK_ADALAT = ["2026-03-14", "2026-05-09", "2026-09-12", "2026-12-12"];
export const nextLokAdalat = (todayIso) => LOK_ADALAT.find((d) => d >= todayIso) || null;

/* ---------------- order-sheet text parser (for the photo reader) ---------------- */
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12 };
const pad = (n) => String(n).padStart(2, "0");
function iso(y, m, d) {
  y = Number(y); m = Number(m); d = Number(d);
  if (y < 100) y += 2000;
  if (y < 2000 || y > 2100 || m < 1 || m > 12 || d < 1) return null;
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return d > last ? null : `${y}-${pad(m)}-${pad(d)}`;
}
const NEXT_KW = /(next\s*date|n\s*\.?\s*d\s*\.?\s*o\s*\.?\s*h|put\s*up|fixed\s*for|adjourned\s*(?:to|till|for)|listed\s*(?:on|for)|to\s*come\s*up|re-?list|अगली\s*(?:तारीख|तिथि)|पेशी|नियत)/i;

/** Find dates (Indian day-first formats and "12 Dec 2026"), the likely next date and its purpose. */
export function parseOrderText(text) {
  const t = String(text || "").replace(/[‐-―]/g, "-");
  const found = [];
  const num = /(\d{1,2})\s*[\/.\-]\s*(\d{1,2})\s*[\/.\-]\s*(\d{4}|\d{2})(?!\d)/g;
  const named = /(\d{1,2})(?:st|nd|rd|th)?\s*[\s.\-]?\s*(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})/gi;
  let m;
  while ((m = num.exec(t))) { const d = iso(m[3], m[2], m[1]); if (d) found.push({ date: d, at: m.index, end: m.index + m[0].length }); }
  while ((m = named.exec(t))) { const d = iso(m[3], MONTHS[m[2].toLowerCase()], m[1]); if (d) found.push({ date: d, at: m.index, end: m.index + m[0].length }); }
  found.sort((a, b) => a.at - b.at);
  if (!found.length) return { dates: [], hearingDate: "", nextDate: "", purpose: "" };
  // Next date: the first date after a "next date / put up / fixed for" keyword; else the latest date if later than the first.
  let next = null;
  const kw = new RegExp(NEXT_KW.source, "gi");
  while ((m = kw.exec(t)) && !next) next = found.find((f) => f.at >= m.index && f.at - m.index < 80) || null;
  const first = found[0];
  if (!next) { const latest = [...found].sort((a, b) => b.date.localeCompare(a.date))[0]; if (latest.date > first.date) next = latest; }
  // Purpose: text right after the next date ("... 12/03/2026 for evidence"), or a keyword before it ("fixed for evidence on ...").
  let purpose = "";
  if (next) {
    const after = t.slice(next.end, next.end + 60).match(/^\s*(?:for|हेतु|को)?\s*([A-Za-zऀ-ॿ][A-Za-zऀ-ॿ .\/&-]{2,40})/);
    const before = t.slice(Math.max(0, next.at - 60), next.at).match(/for\s+([A-Za-z][A-Za-z .\/&-]{2,40}?)\s+(?:on|dt\.?|dated)?\s*$/i);
    for (const c of [after?.[1], before?.[1]]) {
      const cand = (c || "").replace(/[.\s]+$/, "").trim();
      if (cand && decodePurpose(cand)) { purpose = cand.slice(0, 60); break; }
    }
  }
  return { dates: [...new Set(found.map((f) => f.date))], hearingDate: first.date !== next?.date ? first.date : "", nextDate: next ? next.date : "", purpose };
}
