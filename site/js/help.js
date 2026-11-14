// Practical help for litigants: order-sheet stage decoder, CNR helper, cost of delay, "stuck" meter,
// questions for your lawyer, and legal time limits. Pure functions + bilingual content; no network calls.
//
// Legal references were checked against the statutes (indiacode.nic.in), NALSA and eCourts pages.
// They are general information, not legal advice.

/* ---------------- order-sheet stage decoder ---------------- */

// Same normalisation as tareekh_radar/public/build.py normalize_purpose.
export const normPurpose = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9/ ]+/g, " ").replace(/\s+/g, " ").trim();

// Ordered: the first matching rule wins, so specific rules come before general ones.
// Patterns were written against the most common purposes actually recorded in the data (site/data/purposes.json).
export const STAGES = [
  { key: "execution", group: "execution",
    re: /execution|executionof|kurki|attachment|garnishee|possession|\be ?\/ ?r of w|depositing|deposit|payment/,
    en: { t: "Execution / recovery", m: "The case has been decided and the winning side is trying to enforce the decree or order: recovering money, attaching property or taking possession.", n: "The court issues warrants or attachment orders and waits for reports on whether they were carried out." },
    hi: { t: "निष्पादन / वसूली", m: "मामले का फ़ैसला हो चुका है और जीतने वाला पक्ष डिक्री या आदेश लागू करवा रहा है: पैसे की वसूली, संपत्ति कुर्की या कब्ज़ा।", n: "अदालत वारंट या कुर्की आदेश जारी करती है और उनके पालन की रिपोर्ट का इंतज़ार करती है।" } },
  { key: "warrant", group: "service",
    re: /\bn ?b ?w\b|non ?bailable|\bb ?w\b|bailable warrant|warrant|procla?o?mation|proclomation|82 83/,
    en: { t: "Warrant / proclamation", m: "The court has issued a warrant (bailable or non-bailable) or a proclamation to bring an accused or witness to court. \"Unready\" usually means it has not been carried out yet.", n: "The case usually waits until the person is brought to court or appears. If an accused cannot be found, the court can separate their case so others can proceed." },
    hi: { t: "वारंट / उद्घोषणा", m: "अदालत ने किसी अभियुक्त या गवाह को लाने के लिए वारंट (ज़मानती या गैर-ज़मानती) या उद्घोषणा जारी की है। \"Unready\" का अर्थ अक्सर यह है कि अभी इसका पालन नहीं हुआ।", n: "आमतौर पर व्यक्ति के अदालत में आने तक मामला रुका रहता है। अभियुक्त न मिले तो अदालत उसका मामला अलग कर सकती है ताकि बाकी आगे बढ़ें।" } },
  { key: "police_report", group: "filing",
    re: /final form|charge ?sheet|police paper|police report|awa?i?t(ing)? (for )?final|investigation/,
    en: { t: "Waiting for police report / chargesheet", m: "The court is waiting for the police to finish investigating and file their final report (chargesheet or closure report).", n: "Once the report is filed, the court decides whether to take cognizance and summon the accused." },
    hi: { t: "पुलिस रिपोर्ट / आरोप-पत्र की प्रतीक्षा", m: "अदालत पुलिस की जाँच पूरी होने और अंतिम रिपोर्ट (आरोप-पत्र या क्लोज़र रिपोर्ट) दाख़िल होने का इंतज़ार कर रही है।", n: "रिपोर्ट आने के बाद अदालत तय करती है कि संज्ञान लेकर अभियुक्त को बुलाया जाए या नहीं।" } },
  { key: "steps", group: "service",
    re: /\bsteps?\b|talbana|tallabana|batta|process fee|\bp ?f\b/,
    en: { t: "Steps (process fee / addresses)", m: "A party has to \"take steps\": pay the process fee, give correct addresses or copies so that summons or notices can be sent. If steps are not taken, the case cannot move.", n: "After steps are taken, the court sends the summons or notice and waits for it to be served." },
    hi: { t: "कदम (प्रोसेस फ़ीस / पते)", m: "किसी पक्ष को \"कदम\" उठाने हैं: प्रोसेस फ़ीस जमा करना, सही पते या प्रतियाँ देना ताकि समन या नोटिस भेजे जा सकें। ऐसा न होने पर मामला आगे नहीं बढ़ता।", n: "कदम उठाने के बाद अदालत समन या नोटिस भेजती है और तामील का इंतज़ार करती है।" } },
  { key: "service", group: "service",
    re: /summons?|notice|service|serv[ie]|process|\bs ?r\b|sr\/ad|\bad\b|cognizance|cognisance|issuance/,
    en: { t: "Summons / notice / service", m: "The court is trying to inform the other side (or the accused) officially. \"Service pending\" or \"unready\" means the summons or notice has not yet been delivered, or proof of delivery has not come back.", n: "Once service is complete, the other side must appear and respond." },
    hi: { t: "समन / नोटिस / तामील", m: "अदालत दूसरे पक्ष (या अभियुक्त) को औपचारिक सूचना देने की कोशिश कर रही है। \"तामील बाकी\" या \"unready\" का अर्थ है कि समन या नोटिस अभी नहीं पहुँचा या उसकी रिपोर्ट वापस नहीं आई।", n: "तामील होने के बाद दूसरे पक्ष को पेश होकर जवाब देना होता है।" } },
  { key: "appearance", group: "reply",
    re: /appe?a?r|apper|appre|appea|presence|production of accused|talbi|haziri|hazri/,
    en: { t: "Appearance", m: "Parties or the accused are expected to be present in court (personally or through their lawyer) on this date. It is often an early, routine stage.", n: "After everyone appears, the other side files its reply or the court frames charges or issues." },
    hi: { t: "हाज़िरी / पेशी", m: "इस तारीख को पक्षकारों या अभियुक्त को (ख़ुद या वकील के ज़रिए) अदालत में उपस्थित होना है। यह अक्सर शुरुआती, नियमित चरण होता है।", n: "सबके पेश होने के बाद दूसरा पक्ष जवाब दाख़िल करता है या अदालत आरोप/वाद-बिंदु तय करती है।" } },
  { key: "bail", group: "any",
    re: /\bbail\b|surety|bond/,
    en: { t: "Bail", m: "A bail application (or surety/bond papers) is listed. The court hears whether the accused can be released while the case continues.", n: "The court grants or rejects bail, sometimes with conditions such as sureties." },
    hi: { t: "ज़मानत", m: "ज़मानत की अर्ज़ी (या ज़मानतदार/बॉन्ड के कागज़) सूचीबद्ध है। अदालत सुनती है कि मामला चलते रहने तक अभियुक्त को छोड़ा जा सकता है या नहीं।", n: "अदालत ज़मानत देती या नामंज़ूर करती है, कभी-कभी ज़मानतदार जैसी शर्तों के साथ।" } },
  { key: "reply", group: "reply",
    re: /written statement|\bw ?s\b|\breply\b|counter|\bsay\b|objections?|rejoinder|show cause/,
    en: { t: "Written statement / reply", m: "The other side must file its written answer to the case (written statement, reply, counter or objections). In civil suits the law expects the written statement within 30 days of summons, extendable up to 90 days.", n: "After the reply, a civil court frames the issues (the questions to be decided)." },
    hi: { t: "लिखित कथन / जवाब", m: "दूसरे पक्ष को मामले का लिखित जवाब (लिखित कथन, जवाब, काउंटर या आपत्ति) दाख़िल करना है। दीवानी मुकदमों में कानून समन से 30 दिन में, अधिकतम 90 दिन तक, लिखित कथन की अपेक्षा करता है।", n: "जवाब के बाद दीवानी अदालत वाद-बिंदु (तय किए जाने वाले प्रश्न) तय करती है।" } },
  { key: "copies", group: "issues",
    re: /copies|\b207\b|\b208\b/,
    en: { t: "Supply of copies", m: "The accused is being given copies of the police report and documents, which must happen before charges are framed.", n: "Next the court hears arguments on charge." },
    hi: { t: "प्रतियाँ देना", m: "अभियुक्त को पुलिस रिपोर्ट और दस्तावेज़ों की प्रतियाँ दी जा रही हैं, जो आरोप तय होने से पहले ज़रूरी है।", n: "इसके बाद अदालत आरोप पर बहस सुनती है।" } },
  { key: "charge", group: "issues",
    re: /charge|\bplea\b|particulars/,
    en: { t: "Framing of charge / plea", m: "In a criminal case the court decides whether there is enough material to put the accused on trial, and on which charges. The accused is then asked whether they plead guilty.", n: "If the accused pleads not guilty, the trial moves to prosecution evidence." },
    hi: { t: "आरोप तय करना / अभिवाक", m: "आपराधिक मामले में अदालत तय करती है कि अभियुक्त पर मुकदमा चलाने लायक सामग्री है या नहीं, और किन आरोपों पर। फिर अभियुक्त से पूछा जाता है कि वह दोष स्वीकार करता है या नहीं।", n: "दोष अस्वीकार करने पर मुकदमा अभियोजन साक्ष्य के चरण में जाता है।" } },
  { key: "issues", group: "issues",
    re: /\bissues?\b/,
    en: { t: "Framing of issues", m: "In a civil case the court writes down the exact questions in dispute that each side must prove.", n: "Next comes evidence: each side's witnesses and documents." },
    hi: { t: "वाद-बिंदु तय करना", m: "दीवानी मामले में अदालत वे विवादित प्रश्न लिखती है जिन्हें हर पक्ष को साबित करना है।", n: "इसके बाद साक्ष्य: हर पक्ष के गवाह और दस्तावेज़।" } },
  { key: "statement_accused", group: "evidence",
    re: /\b313\b|statement of (the )?accused|\bs ?\/ ?a\b/,
    en: { t: "Statement of accused", m: "After the prosecution evidence, the judge questions the accused about the evidence against them so they can explain.", n: "Then defence evidence (if any), then final arguments." },
    hi: { t: "अभियुक्त का बयान", m: "अभियोजन साक्ष्य के बाद न्यायाधीश अभियुक्त से उसके ख़िलाफ़ साक्ष्य के बारे में पूछते हैं ताकि वह अपनी बात रख सके।", n: "फिर बचाव साक्ष्य (यदि हो), फिर अंतिम बहस।" } },
  { key: "evidence", group: "evidence",
    re: /evid|witness|examination|cross|chief|\bp ?e\b|\bd ?e\b|sworn statement|enquiry|inquiry|deposition|trial|statement of (pw|witness)|further statement|questioning|affirmation|rebut|documents|\bproduction\b/,
    en: { t: "Evidence / witnesses", m: "Witnesses are examined and cross-examined and documents are proved. This is the longest stage in most cases, and the most common stage of pending cases in the data. Delays often come from witnesses not turning up.", n: "When both sides finish their evidence, the case moves to final arguments." },
    hi: { t: "साक्ष्य / गवाही", m: "गवाहों से पूछताछ और जिरह होती है और दस्तावेज़ साबित किए जाते हैं। ज़्यादातर मामलों में यह सबसे लंबा चरण है, और डेटा में लंबित मामलों का सबसे आम चरण भी। देरी अक्सर गवाहों के न आने से होती है।", n: "दोनों पक्षों के साक्ष्य पूरे होने पर मामला अंतिम बहस में जाता है।" } },
  { key: "arguments", group: "arguments",
    re: /argu|\bargs?\b|final hearing|hearing on sentence|sentence/,
    en: { t: "Arguments", m: "Lawyers for both sides explain to the judge why the evidence supports them. \"Hearing on sentence\" comes after a conviction, before the punishment is decided.", n: "After arguments the judge reserves or pronounces judgment." },
    hi: { t: "बहस", m: "दोनों पक्षों के वकील न्यायाधीश को बताते हैं कि साक्ष्य उनके पक्ष में क्यों है। \"सज़ा पर सुनवाई\" दोषसिद्धि के बाद, सज़ा तय होने से पहले होती है।", n: "बहस के बाद न्यायाधीश फ़ैसला सुरक्षित रखते या सुनाते हैं।" } },
  { key: "judgment", group: "judgment",
    re: /judg|pronounce|verdict|\border(s)?\b|disposal|for disposal/,
    en: { t: "Orders / judgment", m: "The case or an application is listed for the court's decision. \"Orders\" can be a final judgment or a decision on a smaller application; the order sheet says which.", n: "After a final judgment you can get a certified copy and, if needed, consider an appeal within the time limit." },
    hi: { t: "आदेश / फ़ैसला", m: "मामला या कोई अर्ज़ी अदालत के निर्णय के लिए सूचीबद्ध है। \"आदेश\" अंतिम फ़ैसला भी हो सकता है या किसी छोटी अर्ज़ी पर निर्णय भी; आदेश-पत्र में यह लिखा होता है।", n: "अंतिम फ़ैसले के बाद आप प्रमाणित प्रति ले सकते हैं और ज़रूरत हो तो समय-सीमा में अपील पर विचार कर सकते हैं।" } },
  { key: "application", group: "any",
    re: /\bi ?a\b|\be ?a\b|\bcmp\b|\bcrp\b|\bcma\b|injunction|\bstay(ed)?\b|interim|amend|temporary|application|petition|\bexh\b/,
    en: { t: "Application (IA) / stay / injunction", m: "A side application inside the main case is being heard, such as a stay, temporary injunction, amendment or delay condonation. The main case often waits until it is decided.", n: "The court decides the application, then the main case resumes from its stage." },
    hi: { t: "अर्ज़ी (आईए) / स्थगन / निषेधाज्ञा", m: "मुख्य मामले के भीतर कोई अर्ज़ी सुनी जा रही है, जैसे स्थगन, अस्थायी निषेधाज्ञा, संशोधन या देरी माफ़ी। अक्सर इसके तय होने तक मुख्य मामला रुका रहता है।", n: "अदालत अर्ज़ी तय करती है, फिर मुख्य मामला अपने चरण से आगे बढ़ता है।" } },
  { key: "settlement", group: "any",
    re: /lok ?adalat|lokadalat|lok nyayalaya|compromise|settlement|mediation|conciliation|\b89\b|\ba ?d ?r\b/,
    en: { t: "Lok Adalat / mediation / settlement", m: "The case has been sent to, or is being considered for, a Lok Adalat, mediation or settlement talks.", n: "If a settlement is reached it is recorded and the case ends. If not, it returns to court at its earlier stage." },
    hi: { t: "लोक अदालत / मध्यस्थता / समझौता", m: "मामला लोक अदालत, मध्यस्थता या समझौता वार्ता के लिए भेजा गया है या उस पर विचार हो रहा है।", n: "समझौता होने पर वह दर्ज होता है और मामला ख़त्म होता है; न होने पर मामला पुराने चरण पर अदालत में लौटता है।" } },
  { key: "admission", group: "filing",
    re: /admission|addmission|registration|defects?|scrutiny|consid|verification|office (note|check)|\b200 cr ?pc\b/,
    en: { t: "Admission / scrutiny", m: "An early stage: the court office checks the filing, or the court decides whether to admit the case or take cognizance.", n: "Once admitted, notice or summons goes to the other side." },
    hi: { t: "स्वीकृति / जाँच", m: "शुरुआती चरण: अदालत का कार्यालय दाख़िले की जाँच करता है, या अदालत तय करती है कि मामला स्वीकार करे या संज्ञान ले।", n: "स्वीकार होने पर दूसरे पक्ष को नोटिस या समन जाता है।" } },
  { key: "records", group: "any",
    re: /records?|\blcr\b|\btcr\b|awa?i?t|await|call for|\breports?\b/,
    en: { t: "Awaiting records / reports", m: "The court is waiting for something from outside: records from another court or office, or a report (for example from police, a commissioner or an expert).", n: "The case usually cannot move until the record or report arrives." },
    hi: { t: "रिकॉर्ड / रिपोर्ट की प्रतीक्षा", m: "अदालत बाहर से किसी चीज़ का इंतज़ार कर रही है: किसी दूसरी अदालत या कार्यालय से रिकॉर्ड, या कोई रिपोर्ट (जैसे पुलिस, कमिश्नर या विशेषज्ञ की)।", n: "रिकॉर्ड या रिपोर्ट आने तक मामला आमतौर पर आगे नहीं बढ़ता।" } },
  { key: "routine", group: "any",
    re: /no sitting|not heard|adjourn|call on|\bmisc|\blist\b|notified|board|further proceedings?|compliance|listed/,
    en: { t: "Routine listing / not taken up", m: "The case was listed for routine or administrative reasons, or was not taken up that day (for example, the judge was on leave). Such dates keep the case alive but rarely move it forward.", n: "Ask what the real pending step is, so the next date can be used for it." },
    hi: { t: "नियमित सूची / सुनवाई नहीं हुई", m: "मामला नियमित या प्रशासनिक कारणों से सूचीबद्ध था, या उस दिन सुना नहीं गया (जैसे न्यायाधीश अवकाश पर थे)। ऐसी तारीखें मामला ज़िंदा रखती हैं पर उसे कम ही आगे बढ़ाती हैं।", n: "पूछें कि असल में कौन-सा कदम बाकी है, ताकि अगली तारीख उसी के लिए काम आए।" } },
  { key: "hearing", group: "any",
    re: /hearing|part heard|\bheard\b/,
    en: { t: "Hearing", m: "A general hearing. The court may hear the main case or an application. \"Part heard\" means the hearing started and will continue.", n: "Check the order sheet for what exactly is to be heard." },
    hi: { t: "सुनवाई", m: "सामान्य सुनवाई। अदालत मुख्य मामला या कोई अर्ज़ी सुन सकती है। \"आंशिक सुनी गई\" का अर्थ है कि सुनवाई शुरू हुई और जारी रहेगी।", n: "आदेश-पत्र में देखें कि ठीक-ठीक क्या सुना जाना है।" } },
];

export function decodePurpose(text) {
  const p = normPurpose(text);
  if (!p) return null;
  return STAGES.find((s) => s.re.test(p)) || null;
}

/* ---------------- questions for your lawyer ---------------- */

export const STAGE_GROUPS = ["filing", "service", "reply", "issues", "evidence", "arguments", "judgment", "execution"];
export const GROUP_LABEL = {
  filing: { en: "Just filed / admission", hi: "अभी दाख़िल / स्वीकृति" },
  service: { en: "Summons / notice / warrant", hi: "समन / नोटिस / वारंट" },
  reply: { en: "Appearance / written statement", hi: "हाज़िरी / लिखित कथन" },
  issues: { en: "Issues / charge", hi: "वाद-बिंदु / आरोप" },
  evidence: { en: "Evidence / witnesses", hi: "साक्ष्य / गवाह" },
  arguments: { en: "Arguments", hi: "बहस" },
  judgment: { en: "Orders / judgment", hi: "आदेश / फ़ैसला" },
  execution: { en: "Execution / recovery", hi: "निष्पादन / वसूली" },
};
export const QUESTIONS = {
  any: {
    en: ["What is the CNR (16-character case number) of my case?", "What exactly is the next date for, and what must be done before it?",
      "Who asked for the last adjournments, and why?", "Can you share a copy (or photo) of each order sheet?",
      "Can this case go to Lok Adalat or mediation?", "What are your fees for each hearing and for the full case?"],
    hi: ["मेरे मामले का CNR (16 अक्षर का केस नंबर) क्या है?", "अगली तारीख ठीक किस लिए है, और उससे पहले क्या करना है?",
      "पिछले स्थगन किसने और क्यों माँगे?", "क्या आप हर आदेश-पत्र की प्रति (या फ़ोटो) दे सकते हैं?",
      "क्या यह मामला लोक अदालत या मध्यस्थता में जा सकता है?", "हर सुनवाई और पूरे मामले की आपकी फ़ीस कितनी है?"],
  },
  filing: { en: ["Has the case been admitted / cognizance taken?", "Are there any defects in the filing I need to fix?"], hi: ["क्या मामला स्वीकार हुआ / संज्ञान लिया गया?", "क्या दाख़िले में कोई कमी है जिसे मुझे ठीक करना है?"] },
  service: { en: ["Has the summons/notice been served? If not, why?", "Do I need to pay process fee or give a new address?", "Can service be done by another mode (registered post, email, publication)?"], hi: ["क्या समन/नोटिस तामील हुआ? नहीं तो क्यों?", "क्या मुझे प्रोसेस फ़ीस देनी है या नया पता देना है?", "क्या तामील दूसरे तरीके (रजिस्टर्ड डाक, ईमेल, प्रकाशन) से हो सकती है?"] },
  reply: { en: ["Has the other side filed its written statement/reply? Is it within time?", "Do I need to be personally present on the next date?"], hi: ["क्या दूसरे पक्ष ने लिखित कथन/जवाब दाख़िल किया? क्या समय पर?", "क्या अगली तारीख पर मेरा ख़ुद उपस्थित होना ज़रूरी है?"] },
  issues: { en: ["What issues/charges has the court framed?", "Do I agree with how the dispute has been described?"], hi: ["अदालत ने कौन-से वाद-बिंदु/आरोप तय किए?", "क्या विवाद का वर्णन सही है?"] },
  evidence: { en: ["Which witnesses are due on the next date? Have summons gone to them?", "Which documents do I need to bring?", "How many witnesses are left on each side?"], hi: ["अगली तारीख पर कौन-से गवाह आने हैं? क्या उन्हें समन गए?", "मुझे कौन-से दस्तावेज़ लाने हैं?", "हर पक्ष के कितने गवाह बाकी हैं?"] },
  arguments: { en: ["Are written arguments being filed?", "When is judgment likely after arguments?"], hi: ["क्या लिखित बहस दाख़िल हो रही है?", "बहस के बाद फ़ैसला कब तक संभावित है?"] },
  judgment: { en: ["Is this a final judgment or an order on an application?", "How do I get a certified copy, and what is the time limit for appeal?"], hi: ["यह अंतिम फ़ैसला है या किसी अर्ज़ी पर आदेश?", "प्रमाणित प्रति कैसे मिलेगी, और अपील की समय-सीमा क्या है?"] },
  execution: { en: ["What has been done to recover the amount or property?", "Can the other side's property or salary be attached?"], hi: ["रकम या संपत्ति की वसूली के लिए क्या किया गया?", "क्या दूसरे पक्ष की संपत्ति या वेतन कुर्क हो सकता है?"] },
};
export function questionsFor(group, lang) {
  const l = lang === "hi" ? "hi" : "en";
  return [...(QUESTIONS[group]?.[l] || []), ...QUESTIONS.any[l]];
}

/* ---------------- CNR helper ---------------- */

// 16 characters: 2-letter state + 2-letter district + 2-digit establishment + 6-digit serial + 4-digit year.
export function parseCNR(input) {
  const s = String(input ?? "").toUpperCase().replace(/[\s-]+/g, "").replace(/(?<=^.{4,})O/g, "0");
  if (s.length !== 16) return { ok: false, error: "len", value: s };
  const m = /^([A-Z]{2})([A-Z]{2})(\d{2})(\d{6})(\d{4})$/.exec(s);
  if (!m) return { ok: false, error: "format", value: s };
  const year = Number(m[5]);
  if (year < 1950 || year > new Date().getUTCFullYear() + 1) return { ok: false, error: "year", value: s };
  return { ok: true, value: s, state: m[1], district: m[2], establishment: m[3], serial: m[4], year };
}

/* ---------------- cost of delay ---------------- */

// DAKSH Access to Justice Survey 2015-16 (9,329 litigants, 305 locations, 24 states): per hearing day,
// civil litigants spent Rs 497 and lost Rs 844 in wages; criminal litigants spent Rs 542 and lost Rs 902.
export const DAKSH = { civil: { spend: 497, lost: 844 }, criminal: { spend: 542, lost: 902 },
  source: "https://dakshindia.org/access-to-justice-survey/" };
export const CRIMINAL_CATS = new Set(["criminal_case", "cheque_bounce", "bail", "maintenance"]);

/** Rough number of hearing days and their cost over a typical case. Returns null when inputs are missing. */
export function costEstimate({ durationDays, gapDays, perDay, people = 1 }) {
  if (!(durationDays > 0) || !(gapDays >= 0) || !(perDay >= 0)) return null;
  const gap = Math.max(gapDays, 7); // at most one hearing a week
  const hearings = Math.max(1, Math.round(durationDays / gap));
  return { hearings, gap, total: hearings * perDay * Math.max(1, people) };
}

/* ---------------- "stuck" meter ---------------- */

// Approximate percentile of x within a distribution known only by a few quantiles ({p50, p75, p90, p95}).
export function approxPercentile(x, q) {
  if (x == null || !q) return null;
  const pts = [[0, 0], [q.p50, 50], [q.p75, 75], [q.p90, 90], [q.p95, 95]].filter(([v]) => v != null);
  if (x <= 0) return 0;
  for (let i = 1; i < pts.length; i++) {
    const [v0, p0] = pts[i - 1], [v1, p1] = pts[i];
    if (x <= v1) return v1 === v0 ? p1 : p0 + ((x - v0) / (v1 - v0)) * (p1 - p0);
  }
  return 97; // beyond the 95th percentile: shown as "more than 95%"
}

/** Practical next-step keys for a delay-check result. Order = priority. */
export function nextSteps(res, category) {
  const steps = [];
  const gapBad = res.verdict === "longer" || res.verdict === "somewhat";
  const veryOld = res.shareStillPendingAtAge != null && res.shareStillPendingAtAge < 0.1;
  steps.push("ns_decode");
  if (gapBad) steps.push("ns_status", "ns_early");
  if (veryOld) steps.push("ns_highcourt");
  if (category === "maintenance") steps.push("ns_maint");
  if (category === "cheque_bounce") steps.push("ns_cheque");
  if (category === "criminal_case" || category === "bail") steps.push("ns_undertrial");
  steps.push("ns_lawyer", "ns_aid", "ns_cost");
  return steps;
}

/* ---------------- deadline calculator ---------------- */

// Checked against the statutes (Limitation Act 1963, NI Act 1881, CPC, MV Act, CPA 2019) and the RBI cheque-validity circular.
// steps are applied in order to the start date. General information, not legal advice.
export const DEADLINES = [
  { key: "cheque_present", steps: [{ months: 3 }], law: "RBI circular (from 1 April 2012); NI Act s.138(a)",
    en: { t: "Cheque bounce 1: present the cheque to the bank", from: "Date written on the cheque" },
    hi: { t: "चेक बाउंस 1: चेक बैंक में जमा करें", from: "चेक पर लिखी तारीख" } },
  { key: "cheque_notice", steps: [{ days: 30 }], law: "NI Act s.138(b)",
    en: { t: "Cheque bounce 2: send the legal demand notice", from: "Date you received the bank's return memo" },
    hi: { t: "चेक बाउंस 2: कानूनी माँग नोटिस भेजें", from: "बैंक का रिटर्न मेमो मिलने की तारीख" } },
  { key: "cheque_pay", steps: [{ days: 15 }], law: "NI Act s.138(c)",
    en: { t: "Cheque bounce 3: last day for the drawer to pay", from: "Date the drawer received your notice" },
    hi: { t: "चेक बाउंस 3: चेक देने वाले के भुगतान का आख़िरी दिन", from: "चेक देने वाले को नोटिस मिलने की तारीख" } },
  { key: "cheque_complaint", steps: [{ days: 16 }, { months: 1 }], law: "NI Act s.142(1)(b)",
    en: { t: "Cheque bounce 4: file the complaint in court (if not paid)", from: "Date the drawer received your notice" },
    hi: { t: "चेक बाउंस 4: अदालत में शिकायत दाख़िल करें (भुगतान न होने पर)", from: "चेक देने वाले को नोटिस मिलने की तारीख" } },
  { key: "ws", steps: [{ days: 30 }], law: "CPC Order VIII Rule 1",
    en: { t: "Civil suit: file the written statement (defendant)", from: "Date the summons was served on you", note: "The court may extend this up to 90 days for reasons; in commercial suits 120 days is a hard limit." },
    hi: { t: "दीवानी वाद: लिखित कथन दाख़िल करें (प्रतिवादी)", from: "आपको समन तामील होने की तारीख", note: "अदालत कारण दर्ज कर 90 दिन तक बढ़ा सकती है; वाणिज्यिक वादों में 120 दिन की कड़ी सीमा है।" } },
  { key: "civil_appeal", steps: [{ days: 30 }], law: "Limitation Act Art. 116(b)", appeal: true,
    en: { t: "Civil appeal to the District Court", from: "Date of the decree or order" },
    hi: { t: "ज़िला अदालत में दीवानी अपील", from: "डिक्री या आदेश की तारीख" } },
  { key: "civil_appeal_hc", steps: [{ days: 90 }], law: "Limitation Act Art. 116(a)", appeal: true,
    en: { t: "Civil appeal to the High Court", from: "Date of the decree or order" },
    hi: { t: "उच्च न्यायालय में दीवानी अपील", from: "डिक्री या आदेश की तारीख" } },
  { key: "crim_appeal", steps: [{ days: 30 }], law: "Limitation Act Art. 115(b)(ii)", appeal: true,
    en: { t: "Criminal appeal against conviction to the Sessions Court", from: "Date of the sentence or order" },
    hi: { t: "दोषसिद्धि के विरुद्ध सत्र न्यायालय में आपराधिक अपील", from: "सज़ा या आदेश की तारीख" } },
  { key: "crim_appeal_hc", steps: [{ days: 60 }], law: "Limitation Act Art. 115(b)(i)", appeal: true,
    en: { t: "Criminal appeal against conviction to the High Court", from: "Date of the sentence or order" },
    hi: { t: "दोषसिद्धि के विरुद्ध उच्च न्यायालय में आपराधिक अपील", from: "सज़ा या आदेश की तारीख" } },
  { key: "revision", steps: [{ days: 90 }], law: "Limitation Act Art. 131", appeal: true,
    en: { t: "Revision petition (civil or criminal)", from: "Date of the decree, order or sentence" },
    hi: { t: "पुनरीक्षण याचिका (दीवानी या आपराधिक)", from: "डिक्री, आदेश या सज़ा की तारीख" } },
  { key: "mact", steps: [{ months: 6 }], law: "Motor Vehicles Act s.166(3) (in force from 1 April 2022)",
    en: { t: "Motor accident compensation claim", from: "Date of the accident", note: "This limit has been challenged in courts; file as early as possible." },
    hi: { t: "मोटर दुर्घटना मुआवज़ा दावा", from: "दुर्घटना की तारीख", note: "इस सीमा को अदालतों में चुनौती दी गई है; जितनी जल्दी हो सके दावा करें।" } },
  { key: "consumer", steps: [{ years: 2 }], law: "Consumer Protection Act 2019 s.69",
    en: { t: "Consumer complaint", from: "Date the problem (cause of action) arose" },
    hi: { t: "उपभोक्ता शिकायत", from: "समस्या (वाद-कारण) उत्पन्न होने की तारीख" } },
];
