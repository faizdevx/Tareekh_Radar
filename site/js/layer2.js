// Before-court help, legal-aid eligibility, notice drafts, journeys, quiz and agenda (pure; no DOM).
// Legal facts were checked against statutes and official portals (see docs/public_site.md). General information only.
import { STAGES, DEADLINES } from "./help.js";

const T = (en, hi) => ({ en, hi });

/* ---------------- 11. "Do I even need court?" ---------------- */
export const PROBLEMS = [
  { key: "consumer", icon: "rupee", t: T("Bad product or service, bank, insurance, phone or online shopping problem", "ख़राब सामान या सेवा, बैंक, बीमा, फ़ोन या ऑनलाइन ख़रीद की समस्या"),
    routes: [
      T("Complain in writing to the company first and keep the reply (or note that none came).", "पहले कंपनी को लिखित शिकायत करें और जवाब रखें (या लिखें कि जवाब नहीं आया)।"),
      T("Call the National Consumer Helpline 1915 or 1800-11-4000 (free, 8 am to 8 pm), WhatsApp 8800001915, or file at consumerhelpline.gov.in. It tries to settle with the company.", "राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 या 1800-11-4000 (मुफ़्त, सुबह 8 से रात 8) पर कॉल करें, व्हाट्सऐप 8800001915, या consumerhelpline.gov.in पर शिकायत करें। यह कंपनी से समाधान की कोशिश करती है।"),
      T("If still unresolved, file a consumer complaint online on e-Daakhil. If you paid up to ₹50 lakh it goes to the District Consumer Commission; there is no fee if you paid up to ₹5 lakh, and no lawyer is needed.", "फिर भी हल न हो तो ई-दाख़िल पर ऑनलाइन उपभोक्ता शिकायत करें। आपने ₹50 लाख तक चुकाए हों तो ज़िला उपभोक्ता आयोग में जाती है; ₹5 लाख तक कोई फ़ीस नहीं, और वकील ज़रूरी नहीं।")],
    links: [["https://consumerhelpline.gov.in/", "consumerhelpline.gov.in"], ["https://edaakhil.nic.in/", "e-Daakhil"]] },
  { key: "police", icon: "scalesc", t: T("A crime happened, or the police will not register my complaint", "अपराध हुआ है, या पुलिस मेरी शिकायत दर्ज नहीं कर रही"),
    routes: [
      T("Report at any police station. Police must register an FIR for a serious (cognizable) offence even if it happened elsewhere (Zero FIR), and give you a free copy.", "किसी भी थाने में रिपोर्ट करें। गंभीर (संज्ञेय) अपराध में पुलिस को एफ़आईआर दर्ज करनी होती है, भले घटना कहीं और हुई हो (ज़ीरो एफ़आईआर), और आपको मुफ़्त प्रति देनी होती है।"),
      T("If they refuse, send the complaint in writing to the Superintendent of Police (SP) of the district (BNSS s.173(4)).", "मना करें तो ज़िले के पुलिस अधीक्षक (एसपी) को लिखित शिकायत भेजें (बीएनएसएस धारा 173(4))।"),
      T("If nothing happens, a lawyer or legal aid can apply to the Magistrate to order an investigation (BNSS s.175(3)); this needs a sworn affidavit and proof that you complained to the SP first. Emergency: call 112.", "फिर भी कुछ न हो तो वकील या कानूनी सहायता मजिस्ट्रेट से जाँच का आदेश माँग सकते हैं (बीएनएसएस धारा 175(3)); इसके लिए शपथ-पत्र और एसपी को पहले की गई शिकायत का सबूत चाहिए। आपात स्थिति: 112 पर कॉल करें।")],
    links: [] },
  { key: "info", icon: "search", t: T("I need information or documents from a government office", "मुझे किसी सरकारी दफ़्तर से जानकारी या दस्तावेज़ चाहिए"),
    routes: [
      T("File an RTI application to the office's Public Information Officer. Fee ₹10 for central offices (states set their own); people below the poverty line pay no fee.", "दफ़्तर के लोक सूचना अधिकारी को आरटीआई आवेदन दें। केंद्रीय दफ़्तरों के लिए ₹10 फ़ीस (राज्य अपनी तय करते हैं); गरीबी रेखा से नीचे के लोगों को फ़ीस नहीं देनी होती।"),
      T("The office must reply within 30 days (48 hours if it concerns someone's life or liberty).", "दफ़्तर को 30 दिन में जवाब देना होता है (किसी के जीवन या स्वतंत्रता से जुड़ा हो तो 48 घंटे में)।"),
      T("No reply or a bad reply: file a first appeal within 30 days to the First Appellate Authority in the same office.", "जवाब न आए या ग़लत हो: 30 दिन के अंदर उसी दफ़्तर के प्रथम अपीलीय अधिकारी को पहली अपील करें।")],
    links: [["https://rtionline.gov.in/", "rtionline.gov.in (central offices)"]] },
  { key: "money", icon: "rupee", t: T("Someone owes me money, or my cheque bounced", "किसी पर मेरा पैसा बकाया है, या मेरा चेक बाउंस हुआ"),
    routes: [
      T("Cheque bounced: send the legal demand notice within 30 days of the bank's return memo. Use the deadline calculator and the notice draft here.", "चेक बाउंस: बैंक के रिटर्न मेमो के 30 दिन के अंदर कानूनी माँग नोटिस भेजें। यहाँ समय-सीमा कैलकुलेटर और नोटिस का मसौदा इस्तेमाल करें।"),
      T("Other money owed: send a written demand, then try mediation or a pre-litigation Lok Adalat through your District Legal Services Authority (free).", "अन्य बकाया: लिखित माँग भेजें, फिर ज़िला विधिक सेवा प्राधिकरण के ज़रिए मध्यस्थता या मुकदमे से पहले की लोक अदालत आज़माएँ (मुफ़्त)।"),
      T("Only then a civil suit. Business-to-business (commercial) disputes must first go through pre-institution mediation (Commercial Courts Act s.12A).", "उसके बाद ही दीवानी मुकदमा। व्यापारिक (वाणिज्यिक) विवादों में पहले संस्थापन-पूर्व मध्यस्थता ज़रूरी है (वाणिज्यिक न्यायालय अधिनियम धारा 12A)।")],
    links: [] },
  { key: "family", icon: "book", t: T("Family, marriage, maintenance or domestic violence", "परिवार, विवाह, भरण-पोषण या घरेलू हिंसा"),
    routes: [
      T("Domestic violence: call the Women Helpline 181 or 112, and contact the Protection Officer of your district under the Domestic Violence Act.", "घरेलू हिंसा: महिला हेल्पलाइन 181 या 112 पर कॉल करें, और घरेलू हिंसा अधिनियम के तहत अपने ज़िले के संरक्षण अधिकारी से संपर्क करें।"),
      T("Women and children always qualify for free legal aid. Ask the District Legal Services Authority (DLSA) for a lawyer and for mediation.", "महिलाओं और बच्चों को हमेशा मुफ़्त कानूनी सहायता मिलती है। ज़िला विधिक सेवा प्राधिकरण (DLSA) से वकील और मध्यस्थता माँगें।"),
      T("Family courts usually send cases to counselling or mediation first; settlements there are faster and cheaper.", "पारिवारिक अदालतें आमतौर पर पहले परामर्श या मध्यस्थता भेजती हैं; वहाँ समझौता तेज़ और सस्ता होता है।")],
    links: [] },
  { key: "work", icon: "clockc", t: T("Unpaid wages or a problem at work", "मज़दूरी नहीं मिली या काम की जगह पर समस्या"),
    routes: [
      T("Write to the employer and keep proof of work and pay (attendance, slips, messages).", "मालिक को लिखें और काम व वेतन के सबूत रखें (हाज़िरी, पर्ची, संदेश)।"),
      T("Go to the district Labour Office; conciliation there is free. Disputes with central-sector employers can be filed on the SAMADHAN portal.", "ज़िला श्रम कार्यालय जाएँ; वहाँ सुलह मुफ़्त है। केंद्रीय क्षेत्र के नियोक्ताओं से विवाद समाधान पोर्टल पर दर्ज कर सकते हैं।"),
      T("Industrial workers qualify for free legal aid.", "औद्योगिक कामगारों को मुफ़्त कानूनी सहायता मिलती है।")],
    links: [["https://samadhan.labour.gov.in/", "SAMADHAN"]] },
  { key: "land", icon: "search", t: T("Land, property, neighbour or rent dispute", "ज़मीन, संपत्ति, पड़ोसी या किराए का विवाद"),
    routes: [
      T("Get the land records first (khatauni / jamabandi / 7-12) from the tehsil or the state land-records website.", "पहले ज़मीन के रिकॉर्ड (खतौनी / जमाबंदी / 7-12) तहसील या राज्य की भूमि-अभिलेख वेबसाइट से लें।"),
      T("Try mediation or a pre-litigation Lok Adalat through the DLSA (free).", "DLSA के ज़रिए मध्यस्थता या मुकदमे से पहले की लोक अदालत आज़माएँ (मुफ़्त)।"),
      T("Rent and eviction rules are different in every state, so ask the DLSA or a lawyer before sending any notice.", "किराए और बेदख़ली के नियम हर राज्य में अलग हैं, इसलिए कोई नोटिस भेजने से पहले DLSA या वकील से पूछें।")],
    links: [] },
];

/* ---------------- 15. Free legal aid eligibility (LSA Act s.12) ---------------- */
export const AID_QUESTIONS = [
  { key: "woman_child", g: "I am a woman / child", t: T("Is the person a woman or a child (under 18)?", "क्या व्यक्ति महिला या बच्चा (18 से कम) है?") },
  { key: "sc_st", g: "I belong to a Scheduled Caste / Scheduled Tribe", t: T("Is the person from a Scheduled Caste or Scheduled Tribe?", "क्या व्यक्ति अनुसूचित जाति या अनुसूचित जनजाति से है?") },
  { key: "disabled", g: "I am a person with a disability", t: T("Does the person have a disability?", "क्या व्यक्ति दिव्यांग है?") },
  { key: "custody", g: "I am in custody", t: T("Is the person in custody (jail, police custody, protective or juvenile home, psychiatric hospital)?", "क्या व्यक्ति हिरासत में है (जेल, पुलिस हिरासत, संरक्षण या किशोर गृह, मनोरोग अस्पताल)?") },
  { key: "victim", g: "I am a victim of trafficking, forced labour, or a disaster or violence covered by Section 12", t: T("Is the person a victim of trafficking or forced labour, or of a disaster, ethnic or caste violence, flood, drought, earthquake or industrial disaster?", "क्या व्यक्ति मानव तस्करी या बेगार, या आपदा, जातीय या जातिगत हिंसा, बाढ़, सूखा, भूकंप या औद्योगिक आपदा का पीड़ित है?") },
  { key: "workman", g: "I am an industrial workman", t: T("Is the person an industrial worker?", "क्या व्यक्ति औद्योगिक कामगार है?") },
  { key: "income", g: "my annual income is below the limit fixed by the State Government", t: T("Is the person's yearly income below the limit set by their state? (A sworn statement of income is usually enough.)", "क्या व्यक्ति की सालाना आय राज्य की तय सीमा से कम है? (आय का शपथ-पत्र आमतौर पर काफ़ी होता है।)") },
];
/** Any "yes" means the person is likely eligible under Section 12; the DLSA decides. */
export const AID_APPLY = "https://nalsa.gov.in/services/legal-aid/apply-for-legal-aid";
export function aidEligible(answers) {
  const yes = AID_QUESTIONS.filter((q) => answers[q.key] === true).map((q) => q.key);
  return { likely: yes.length > 0, grounds: yes };
}

/* ---------------- 13. Notice and letter drafts ---------------- */
// Each field: [key, label EN, label HI, type]. Output text is English (as filed in most district courts).
export const NOTICES = {
  cheque: {
    t: T("Cheque bounce: legal demand notice (NI Act s.138)", "चेक बाउंस: कानूनी माँग नोटिस (एनआई एक्ट धारा 138)"),
    note: T("Send within 30 days of receiving the bank's return memo, by registered or speed post, and keep the receipt and delivery proof.", "बैंक का रिटर्न मेमो मिलने के 30 दिन के अंदर रजिस्टर्ड या स्पीड पोस्ट से भेजें, और रसीद व पहुँचने का सबूत रखें।"),
    fields: [["from", "Your name and address", "आपका नाम और पता", "area"], ["to", "Name and address of the person who gave the cheque", "चेक देने वाले का नाम और पता", "area"],
      ["chequeNo", "Cheque number", "चेक नंबर"], ["chequeDate", "Cheque date", "चेक की तारीख", "date"], ["amount", "Amount (₹)", "रकम (₹)"],
      ["bank", "Bank and branch of the cheque", "चेक का बैंक और शाखा"], ["memoDate", "Date you received the bank's return memo", "बैंक का रिटर्न मेमो मिलने की तारीख", "date"],
      ["reason", "Reason written on the memo (e.g. funds insufficient)", "मेमो पर लिखा कारण (जैसे अपर्याप्त राशि)"], ["purpose", "What the cheque was for (loan, goods, etc.)", "चेक किसलिए था (कर्ज़, सामान आदि)", "area"]],
    build: (v, today) => `LEGAL NOTICE UNDER SECTION 138 OF THE NEGOTIABLE INSTRUMENTS ACT, 1881

Date: ${today}

From:
${v.from}

To:
${v.to}

Sir/Madam,

1. You issued cheque no. ${v.chequeNo} dated ${v.chequeDate}, drawn on ${v.bank}, for Rs. ${v.amount}, towards ${v.purpose}.
2. The cheque was presented for payment and was returned unpaid with the remark "${v.reason}". I received the bank's return memo on ${v.memoDate}.
3. I hereby demand that you pay the said amount of Rs. ${v.amount} within 15 (fifteen) days of receiving this notice.
4. If you fail to pay within that time, I will be constrained to initiate proceedings against you under Sections 138 and 142 of the Negotiable Instruments Act, 1881, at your risk as to costs and consequences.

Yours faithfully,

(Signature)
${v.from.split("\n")[0] || ""}
` },
  consumer: {
    t: T("Consumer complaint letter to a company", "कंपनी को उपभोक्ता शिकायत पत्र"),
    note: T("Send this first. If it is not resolved, use the National Consumer Helpline (1915) or file on e-Daakhil, attaching this letter.", "पहले यह भेजें। हल न हो तो राष्ट्रीय उपभोक्ता हेल्पलाइन (1915) या ई-दाख़िल पर शिकायत करें और यह पत्र लगाएँ।"),
    fields: [["from", "Your name, address and phone", "आपका नाम, पता और फ़ोन", "area"], ["to", "Company name and address (or customer-care email)", "कंपनी का नाम और पता (या कस्टमर-केयर ईमेल)", "area"],
      ["item", "Product or service, order/bill number and date", "सामान या सेवा, ऑर्डर/बिल नंबर और तारीख", "area"], ["amount", "Amount paid (₹)", "दी गई रकम (₹)"],
      ["problem", "What went wrong (dates, what you were told)", "क्या गड़बड़ हुई (तारीखें, आपसे क्या कहा गया)", "area"], ["want", "What you want (refund, replacement, repair, compensation)", "आप क्या चाहते हैं (रिफ़ंड, बदलना, मरम्मत, मुआवज़ा)", "area"]],
    build: (v, today) => `Date: ${today}

From:
${v.from}

To:
${v.to}

Subject: Complaint about ${v.item.split("\n")[0]}

Sir/Madam,

1. I purchased/availed ${v.item} and paid Rs. ${v.amount}.
2. ${v.problem}
3. This is a deficiency in service / defect in goods under the Consumer Protection Act, 2019.
4. I request you to ${v.want} within 15 days of this letter.
5. If this is not resolved, I will approach the Consumer Commission without further notice, and will claim compensation and costs.

Yours faithfully,

(Signature)
${v.from.split("\n")[0] || ""}
` },
  rti: {
    t: T("RTI application (information from a government office)", "आरटीआई आवेदन (सरकारी दफ़्तर से जानकारी)"),
    note: T("Attach the fee (₹10 for central offices; state rules vary) or proof that you are below the poverty line. Keep a copy and the postal receipt.", "फ़ीस (केंद्रीय दफ़्तरों के लिए ₹10; राज्य के नियम अलग) या गरीबी रेखा से नीचे होने का सबूत लगाएँ। प्रति और डाक रसीद रखें।"),
    fields: [["office", "Office name and address (Public Information Officer)", "दफ़्तर का नाम और पता (लोक सूचना अधिकारी)", "area"], ["from", "Your name and address", "आपका नाम और पता", "area"],
      ["info", "Exactly what information or copies you want (one per line)", "ठीक-ठीक कौन-सी जानकारी या प्रतियाँ चाहिए (हर पंक्ति में एक)", "area"], ["period", "Time period it covers", "किस अवधि की"],
      ["bpl", "Below poverty line? (yes/no)", "गरीबी रेखा से नीचे? (हाँ/नहीं)"]],
    build: (v, today) => `APPLICATION UNDER SECTION 6(1) OF THE RIGHT TO INFORMATION ACT, 2005

To,
The Public Information Officer,
${v.office}

Date: ${today}

1. Name and address of applicant:
${v.from}

2. Information required (period: ${v.period}):
${v.info.split("\n").filter(Boolean).map((x, i) => `   (${i + 1}) ${x}`).join("\n")}

3. ${/^(y|yes|haan|हाँ)/i.test(v.bpl.trim()) ? "I belong to the Below Poverty Line category; a copy of proof is enclosed, so no fee is payable." : "The application fee is enclosed."}

4. I request that the information be provided within 30 days as required under Section 7(1) of the Act.

Signature of applicant
` },
  lawyer: {
    t: T("Letter to my lawyer asking for my case file and status", "वकील को पत्र: मेरे मामले की फ़ाइल और स्थिति माँगना"),
    note: T("Useful when you are not being told anything, or when you want to change lawyers.", "जब आपको कुछ नहीं बताया जा रहा हो, या वकील बदलना चाहते हों, तब काम आता है।"),
    fields: [["from", "Your name and phone", "आपका नाम और फ़ोन", "area"], ["lawyer", "Lawyer's name", "वकील का नाम"], ["caseno", "Case number / CNR and court", "केस नंबर / CNR और अदालत"],
      ["change", "Are you changing lawyers? (yes/no)", "क्या आप वकील बदल रहे हैं? (हाँ/नहीं)"]],
    build: (v, today) => `Date: ${today}

To,
${v.lawyer}

Subject: My case ${v.caseno}

Dear Sir/Madam,

Please let me know in writing:
1. The present stage of my case and the next date of hearing, with its purpose.
2. Who sought each adjournment so far and why.
3. Copies of all order sheets, pleadings and documents filed in my case.
${/^(y|yes|haan|हाँ)/i.test(v.change.trim()) ? "\nI have decided to engage another advocate. Please return my case papers and give your no-objection so that the new advocate can file a vakalatnama.\n" : ""}
Thank you.

${v.from}
` },
};
/** Fill a template; missing fields become clearly visible blanks. */
export function buildNotice(key, values, todayText) {
  const n = NOTICES[key];
  const v = Object.fromEntries(n.fields.map(([k]) => [k, String(values[k] ?? "").trim() || "[ ............ ]"]));
  return n.build(v, todayText);
}

/* ---------------- 14. Journeys (steps for common disputes) ---------------- */
export const JOURNEYS = {
  cheque_bounce: [T("Cheque returned by bank (return memo)", "बैंक से चेक लौटा (रिटर्न मेमो)"), T("Demand notice within 30 days", "30 दिन में माँग नोटिस"),
    T("15 days for the other side to pay", "दूसरे पक्ष को भुगतान के लिए 15 दिन"), T("Complaint in court within 1 month after that", "उसके 1 महीने के अंदर अदालत में शिकायत"),
    T("Summons to the accused; appearance and bail", "अभियुक्त को समन; हाज़िरी और ज़मानत"), T("Evidence and arguments (settlement possible at any stage)", "साक्ष्य और बहस (किसी भी चरण में समझौता संभव)"), T("Judgment", "फ़ैसला")],
  motor_accident: [T("FIR and medical records", "एफ़आईआर और मेडिकल रिकॉर्ड"), T("Claim to the Motor Accident Claims Tribunal within 6 months", "6 महीने के अंदर मोटर दुर्घटना दावा अधिकरण में दावा"),
    T("Notice to the owner and insurance company", "मालिक और बीमा कंपनी को नोटिस"), T("Reply and evidence (income, disability, bills)", "जवाब और साक्ष्य (आय, विकलांगता, बिल)"), T("Award; settlement at Lok Adalat is common", "अवार्ड; लोक अदालत में समझौता आम है")],
  maintenance: [T("Application for maintenance (and interim maintenance)", "भरण-पोषण (और अंतरिम भरण-पोषण) की अर्ज़ी"), T("Notice to the other side", "दूसरे पक्ष को नोटिस"),
    T("Interim maintenance order (law asks for 60 days, as far as possible)", "अंतरिम भरण-पोषण आदेश (कानून यथासंभव 60 दिन कहता है)"), T("Evidence about income and needs", "आय और ज़रूरतों पर साक्ष्य"), T("Final order; recovery if not paid", "अंतिम आदेश; भुगतान न हो तो वसूली")],
  civil_suit: [T("Legal notice and land/property records", "कानूनी नोटिस और ज़मीन/संपत्ति के रिकॉर्ड"), T("Suit filed; court fee paid", "मुकदमा दायर; कोर्ट फ़ीस जमा"), T("Summons and written statement (30–90 days)", "समन और लिखित कथन (30–90 दिन)"),
    T("Issues framed", "वाद-बिंदु तय"), T("Evidence of both sides", "दोनों पक्षों के साक्ष्य"), T("Arguments and judgment; then execution of the decree", "बहस और फ़ैसला; फिर डिक्री का निष्पादन")],
  matrimonial: [T("Counselling / mediation at the family court", "पारिवारिक अदालत में परामर्श / मध्यस्थता"), T("Petition and notice to the other side", "याचिका और दूसरे पक्ष को नोटिस"),
    T("Reply; interim maintenance and custody applications", "जवाब; अंतरिम भरण-पोषण और अभिरक्षा की अर्ज़ियाँ"), T("Evidence", "साक्ष्य"), T("Decree (mutual-consent cases are much faster)", "डिक्री (आपसी सहमति के मामले बहुत तेज़)")],
  criminal_case: [T("FIR or complaint", "एफ़आईआर या शिकायत"), T("Investigation and chargesheet", "जाँच और आरोप-पत्र"), T("Cognizance and summons; bail", "संज्ञान और समन; ज़मानत"),
    T("Charges framed", "आरोप तय"), T("Prosecution and defence evidence", "अभियोजन और बचाव साक्ष्य"), T("Arguments and judgment", "बहस और फ़ैसला")],
};

/* ---------------- 19. Training quiz (built from the glossary and deadlines) ---------------- */
function rng(seed) { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
function shuffle(arr, r) { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
/** Multiple-choice questions: stage meanings and legal time limits. Deterministic for a seed. */
export function buildQuiz(lang, n = 8, seed = 7) {
  const L = (x) => x[lang] || x.en;
  const r = rng(seed);
  const qs = [];
  for (const st of shuffle(STAGES, r).slice(0, Math.ceil(n * 0.6))) {
    const wrong = shuffle(STAGES.filter((x) => x.key !== st.key), r).slice(0, 3).map((x) => L(x).t);
    qs.push({ q: lang === "hi" ? `"${L(st).m.split("।")[0]}।" यह किस चरण का वर्णन है?` : `Which stage is this? "${L(st).m.split(".")[0]}."`,
      options: shuffle([L(st).t, ...wrong], r), answer: L(st).t });
  }
  const days = (d) => d.steps.map((s) => (s.days ? `${s.days} ${lang === "hi" ? "दिन" : "days"}` : s.months ? `${s.months} ${lang === "hi" ? "महीने" : "months"}` : `${s.years} ${lang === "hi" ? "साल" : "years"}`)).join(" + ");
  const pool = DEADLINES.filter((d) => d.steps.length === 1);
  for (const d of shuffle(pool, r).slice(0, n - qs.length)) {
    const right = days(d);
    const wrong = [...new Set(shuffle(pool.filter((x) => days(x) !== right), r).map(days))].slice(0, 3);
    qs.push({ q: lang === "hi" ? `${L(d).t}: समय-सीमा कितनी है? (${L(d).from} से)` : `${L(d).t}: how long do you have? (from: ${L(d).from})`,
      options: shuffle([right, ...wrong], r), answer: right, law: d.law });
  }
  return qs;
}

/* ---------------- 21. Agenda across cases (this week, clashes) ---------------- */
/** Groups the next dates of all cases; flags dates where two or more cases are listed (possible clash). */
export function agenda(cases, todayIso, nextOf) {
  const plus7 = new Date(Date.parse(todayIso + "T00:00:00Z") + 7 * 86400000).toISOString().slice(0, 10);
  const rows = cases.map((c) => ({ c, next: nextOf(c) })).filter((x) => x.next);
  const byDate = {};
  for (const x of rows) (byDate[x.next] ||= []).push(x.c.id);
  const clash = new Set(Object.values(byDate).filter((ids) => ids.length > 1).flat());
  const g = { overdue: [], today: [], week: [], later: [] };
  for (const x of rows.sort((a, b) => a.next.localeCompare(b.next))) {
    const k = x.next < todayIso ? "overdue" : x.next === todayIso ? "today" : x.next <= plus7 ? "week" : "later";
    g[k].push({ ...x, clash: clash.has(x.c.id) });
  }
  return g;
}

/* ---------------- rankings helpers ---------------- */
/** Position of a district in a ranking list (1 = fastest) and the list length. */
export function rankOf(rows, districtId) {
  const i = (rows || []).findIndex((r) => r[0] === districtId);
  return i < 0 ? null : { rank: i + 1, of: rows.length };
}
