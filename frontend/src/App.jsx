import { Fragment, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  Calculator,
  Play,
  RotateCcw,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_KANIT_API_BASE || "/api";
const API_KEY = import.meta.env.VITE_KANIT_API_KEY || "";

const LIVE_STAGES = [
  "Rapor metni okunuyor",
  "Belge ajanı alanları çıkarıyor",
  "Kontrol listesi ve beceri ontolojisi çalışıyor",
  "Mentor görevi ve operational readiness skoru üretiliyor",
];

const PUBLIC_REPORT_SAMPLES = [
  {
    id: "kaman",
    title: "Kaman Tedarikçi 8D Formu",
    source: "Kaman",
    url: "https://kaman.com/wp-content/uploads/2021/02/qf4.1.859-supplierrequestcorrectiveaction-8d-form.pdf",
    note: "Tedarikçi düzeltici aksiyon ve 8D formu. PDF olarak indirip aynen yüklenebilir.",
    seedText:
      "Tedarikçi düzeltici aksiyon talebi - 8D yanıtı. Problem: Giriş muayenesinde yanlış kimlik etiketi taşıyan uygunsuz tedarikçi parçası bulundu. Muhafaza: Şüpheli stok ayrıldı ve müşteri hattı korumaya alındı. Kök neden: Operatör, etiket revizyonundan sonra eski iş talimatını kullandı. Düzeltici aksiyon: İş talimatı güncellendi ve etiket doğrulama adımı eklendi. Önleyici aksiyon: Katmanlı proses denetimi planlandı. Etkinlik doğrulaması: Eklenmedi. Sorumlu: Tanımlanmadı. Termin: Tanımlanmadı.",
  },
  {
    id: "yf",
    title: "YF SCAR / 8D Yanıtı",
    source: "YF",
    url: "https://yf.com/wp-content/uploads/2024/06/FRM-QCP-08_Supplier-Corrective-Action-Response-SCAR-8D-Response_REV.-F.pdf",
    note: "SCAR-8D yanıt formatı. Müşteri şikayeti kapanış yapısı net biçimde görülebilir.",
    seedText:
      "Tedarikçi düzeltici aksiyon talebi - SCAR 8D yanıtı. Uygunsuzluk tanımı: Müşteri, karışık revizyon etiketli parçalar teslim aldı. Geçici muhafaza: Depo karantinası ve yüzde yüz ayıklama tamamlandı. Kök neden: Revizyon değişikliği e-posta ile iletildi ancak istasyon kontrol listesine eklenmedi. Düzeltici aksiyon: Kontrol listesi güncellendi ve operatör tekrar eğitimi tamamlandı. Doğrulama: Önce/sonra kanıtı, örneklem büyüklüğü ve tekrar denetim sonucu yok. Önleme: Benzer etiket istasyonları gözden geçirilecek.",
  },
  {
    id: "safetyculture",
    title: "SafetyCulture 8D Şablonu",
    source: "SafetyCulture",
    url: "https://safetyculture.com/library/manufacturing/8d-reportp5ycY",
    note: "8D düzeltici aksiyon şablonu; form alanları KANIT çıkarımına iyi eşleşir.",
    seedText:
      "8D düzeltici aksiyon raporu. D2 Problem: Üç braket, bükülmüş montaj kenarı nedeniyle final muayeneden kaldı. D3 Muhafaza: Final stok izole edildi ve müşteri sevkiyatı durduruldu. D4 Kök neden: Fikstür aşınması bakım kontrol listesi tarafından yakalanmadı. D5 Düzeltici aksiyon: Fikstür değiştirildi ve strok sayacı eklendi. D6 Doğrulama: Kısa açıklama sorunun giderildiğini söylüyor, ancak ölçüm kaydı veya etkinlik kontrolü yok. D7 Önleme: Bakım SOP güncellemesi planlandı.",
  },
];

const SAMPLE_TEMPLATES = [
  {
    id: "8d",
    type: "8D Raporu",
    title: "Fren Kaliper Braketi",
    hint: "Boyutsal sapma · D1–D8 eksiksiz · Otomotiv tedarik",
    file: "/sample-8d-brake-caliper.txt",
  },
  {
    id: "capa",
    type: "CAPA Raporu",
    title: "Direksiyon Mili Tork Sapması",
    hint: "Alet kalibrasyon · 5 Neden · Etkinlik doğrulama",
    file: "/sample-capa-action-plan.txt",
  },
];

const FIELD_LABELS = {
  problem_statement: "D2 Problem",
  containment_action: "D3 Muhafaza",
  root_cause: "D4 Kök Neden",
  corrective_action: "D5 Düzeltici",
  preventive_action: "D7 Önleyici",
  effectiveness_check: "D6 Etkinlik",
  owner: "Sorumlu",
  due_date: "Termin",
};

function scrollToElement(element, reducedMotion) {
  if (!element) return;
  const top = element.getBoundingClientRect().top + window.scrollY - 58;
  window.scrollTo({ top, behavior: reducedMotion ? "auto" : "smooth" });
}

function App() {
  const [health, setHealth] = useState(null);
  const [healthFailed, setHealthFailed] = useState(false);
  const [mode, setMode] = useState("demo");
  const [phase, setPhase] = useState("idle");
  const [liveIncident, setLiveIncident] = useState(null);
  const [liveError, setLiveError] = useState(null);
  const [loadingStage, setLoadingStage] = useState(0);
  const [displayMode, setDisplayMode] = useState(() => {
    try {
      return new URLSearchParams(window.location.search).get("mode") === "lab" ? "lab" : "demo";
    } catch {
      return "demo";
    }
  });
  const [selectedSampleId, setSelectedSampleId] = useState(PUBLIC_REPORT_SAMPLES[0].id);
  const [caseText, setCaseText] = useState(PUBLIC_REPORT_SAMPLES[0].seedText);
  const [caseFile, setCaseFile] = useState(null);
  const [defectPhoto, setDefectPhoto] = useState(null);
  const [correctivePhoto, setCorrectivePhoto] = useState(null);
  const [measurementPhoto, setMeasurementPhoto] = useState(null);
  const [meta, setMeta] = useState({
    employee_code: "task-route-014",
    role_code: "quality_engineer",
    team_code: "tedarikci_kalite_a",
    station_code: "final_muayene",
  });
  const [gateData, setGateData] = useState(null);
  const [gateAcknowledged, setGateAcknowledged] = useState(false);
  const [mentorApproved, setMentorApproved] = useState(false);
  const [mentorApproving, setMentorApproving] = useState(false);
  const [roiInputs, setRoiInputs] = useState({
    quality_engineers_in_scope: "3",
    review_hours_saved_per_engineer_per_week: "2",
    loaded_hourly_cost_try: "900",
    incidents_per_month: "40",
    repeated_evidence_gap_rate: "0.25",
    mentor_closure_hours_before: "48",
    mentor_closure_hours_after: "24",
  });
  const [roiImpact, setRoiImpact] = useState(null);
  const [roiError, setRoiError] = useState(null);
  const [roiLoading, setRoiLoading] = useState(false);
  const [trialTab, setTrialTab] = useState("sample");
  const [selectedTemplate, setSelectedTemplate] = useState("8d");
  const [sampleTexts, setSampleTexts] = useState({ "8d": "", "capa": "" });
  const fileInputRef = useRef(null);
  const timers = useRef([]);
  const demoRef = useRef(null);
  const labRef = useRef(null);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    checkHealth();
    SAMPLE_TEMPLATES.forEach(({ id, file }) => {
      fetch(file)
        .then((r) => r.text())
        .then((t) => setSampleTexts((prev) => ({ ...prev, [id]: t })))
        .catch(() => {});
    });
    return clearTimers;
  }, []);

  const activeSampleText = sampleTexts[selectedTemplate] || "";
  const isLive = mode === "live";
  const isRunning = phase !== "idle";
  const isLoading = phase === "loading";
  const hasMentor = phase === "mentor";
  const isAnalyzingLive = isLive && isLoading;
  const statusLabel = health?.status === "ok" ? "Canlı sunucu" : healthFailed ? "Sunucu çevrimdışı" : "Kontrol ediliyor";
  const gateStatus = mentorApproved
    ? "CLEARED"
    : gateAcknowledged
    ? "NEEDS_MENTOR_REVIEW"
    : gateData?.gate_status || "ACTION_REQUIRED";

  async function checkHealth() {
    try {
      const response = await fetch(`${API_BASE}/health`, { headers: apiHeaders() });
      if (!response.ok) throw new Error(`health ${response.status}`);
      const data = await response.json();
      setHealth(data);
      setHealthFailed(false);
    } catch {
      setHealth(null);
      setHealthFailed(true);
    }
  }

  function useSample(sample) {
    setSelectedSampleId(sample.id);
    setCaseText(sample.seedText);
    setCaseFile(null);
    setLiveError(null);
    setMode("live");
    setPhase("idle");
  }

  async function analyzeLiveReport() {
    clearTimers();
    setMode("live");
    setPhase("loading");
    setLiveIncident(null);
    setLiveError(null);
    setLoadingStage(0);

    LIVE_STAGES.forEach((_, index) => {
      schedule(() => setLoadingStage(index), index * 520);
    });

    try {
      const form = new FormData();
      form.append("incident_type", "quality_8d_capa");
      Object.entries(meta).forEach(([key, value]) => {
        if (value) form.append(key, value);
      });
      const textToSend = caseText.trim() || (trialTab === "sample" ? activeSampleText.trim() : "");
      if (textToSend) form.append("case_text", textToSend);
      if (caseFile) form.append("case_file", caseFile);
      if (defectPhoto) form.append("defect_photo", defectPhoto);
      if (correctivePhoto) form.append("corrective_photo", correctivePhoto);
      if (measurementPhoto) form.append("measurement_photo", measurementPhoto);

      if (!textToSend && !caseFile) {
        throw new Error("Analiz için rapor metni yaz veya bir dosya yükle.");
      }

      const response = await fetch(`${API_BASE}/incidents/analyze`, {
        method: "POST",
        headers: apiHeaders(),
        body: form,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(data?.detail || `Sunucu ${response.status}`);
      }
      setLiveIncident(data);
      setPhase("score");
      if (prefersReducedMotion) {
        setPhase("mentor");
      } else {
        schedule(() => setPhase("mentor"), 900);
      }
    } catch (error) {
      setLiveError(error.message || "Analiz başarısız oldu.");
      setPhase("error");
    }
  }

  async function estimateRoi() {
    setRoiLoading(true);
    setRoiError(null);
    setRoiImpact(null);
    try {
      const hypothesisInputs = Object.fromEntries(
        Object.entries(roiInputs).map(([key, value]) => [key, Number(value || 0)]),
      );
      const response = await fetch(`${API_BASE}/pilot/roi-hypothesis`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...apiHeaders() },
        body: JSON.stringify(hypothesisInputs),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Sunucu ${response.status}`);
      setRoiImpact(data);
    } catch (error) {
      setRoiError(error.message || "Pilot ROI varsayımı hesaplanamadı.");
    } finally {
      setRoiLoading(false);
    }
  }

  async function approveMentor() {
    setMentorApproving(true);
    const task = liveIncident?.learning_tasks?.[0];
    const taskId = task?.task_id || null;
    const employeeCode = task?.employee_code || meta.employee_code || "task-route-014";
    if (taskId && !healthFailed) {
      try {
        await fetch(`${API_BASE}/mentor-reviews`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...apiHeaders() },
          body: JSON.stringify({
            task_id: taskId,
            employee_code: employeeCode,
            skill_id: "effectiveness_verification",
            reviewer_code: "mentor-demo-01",
            decision: "approved",
            comment: "Etkinlik doğrulama kanıtı yeterli. Vardiya hazır.",
          }),
        });
      } catch {
        // Simulation continues even if API call fails
      }
    }
    setMentorApproved(true);
    setMentorApproving(false);
  }

  function resetDemo() {
    clearTimers();
    setMode("demo");
    setPhase("idle");
    setLiveIncident(null);
    setLiveError(null);
    setLoadingStage(0);
    setGateData(null);
    setGateAcknowledged(false);
    setMentorApproved(false);
    setMentorApproving(false);
  }

  function handleFileSelect(file) {
    const isText = file.type === "text/plain" || /\.(txt|csv)$/i.test(file.name);
    if (isText) {
      const reader = new FileReader();
      reader.onload = (ev) => { setCaseText(ev.target.result || ""); setCaseFile(null); setTrialTab("text"); };
      reader.readAsText(file, "utf-8");
    } else {
      setCaseFile(file);
      setCaseText("");
    }
  }

  function schedule(callback, delay) {
    const timer = window.setTimeout(callback, delay);
    timers.current.push(timer);
  }

  function clearTimers() {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
  }

  function scrollToDemo() {
    scrollToElement(demoRef.current, prefersReducedMotion);
  }

  function openLab() {
    setDisplayMode("lab");
    setTimeout(() => scrollToElement(labRef.current, prefersReducedMotion), 150);
  }

  return (
    <div className="kanit-app">
      {/* Fixed nav */}
      <SiteNav onDemo={scrollToDemo} onOpenLab={openLab} health={health} healthFailed={healthFailed} />

      {isLive && <LiveActionSheet incident={liveIncident} visible={hasMentor && Boolean(liveIncident)} />}

      {/* ── SECTION 1: HERO ────────────────────────── */}
      <HeroSection onScrollToDemo={scrollToDemo} onOpenLab={openLab} prefersReducedMotion={prefersReducedMotion} />

      {/* ── SECTION 2: PROBLEM ─────────────────────── */}
      <ProblemSection />

      {/* ── SECTION 2.5: LEARNING LOOP ─────────────── */}
      <LearningLoopSection />

      {/* ── SECTION 3: HOW IT WORKS ────────────────── */}
      <HowSection />

      {/* ── SECTION 4: LIVE DEMO ───────────────────── */}
      <section
        id="demo"
        ref={demoRef}
        className={`demo-theater mode-${mode} phase-${phase}`}
        aria-label="KANIT canlı demo"
      >
        <EvidenceField active={isRunning} reducedMotion={prefersReducedMotion} />

        <div className="demo-theater-inner">
          <div className="demo-theater-header">
            <motion.span
              className="section-eyebrow dark"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              Deneme Ekranı
            </motion.span>
            <motion.h2
              className="demo-theater-headline"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            >
              8D / CAPA Raporunu Analiz Et
            </motion.h2>
          </div>

          {isLive ? (
            <section className="risk-theater" aria-live="polite">
              <div className="glass-stage live-stage">
                <div className="stage-toolbar">
                  <span>Analiz çalışıyor</span>
                  <div className="toolbar-status">
                    <StatusPill label={statusLabel} tone={health?.live_ai_enabled && !health?.allow_mock ? "verified" : "risk"} />
                  </div>
                </div>
                <LiveAnalysisStage
                  incident={liveIncident}
                  phase={phase}
                  error={liveError}
                  selectedSample={PUBLIC_REPORT_SAMPLES.find((s) => s.id === selectedSampleId)}
                />
              </div>
            </section>
          ) : (
            <div className="trial-card">
              <div className="trial-tabs" role="tablist">
                {[
                  { id: "sample", label: "Örnek Rapor ile Dene", icon: <FileText size={14} /> },
                  { id: "text",   label: "Metin Yapıştır",        icon: <Play size={14} /> },
                  { id: "file",   label: "Dosya Yükle",           icon: <UploadCloud size={14} /> },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    role="tab"
                    aria-selected={trialTab === tab.id}
                    className={`trial-tab${trialTab === tab.id ? " active" : ""}`}
                    onClick={() => setTrialTab(tab.id)}
                    type="button"
                  >
                    {tab.icon} {tab.label}
                  </button>
                ))}
              </div>

              <div className="trial-content">
                {trialTab === "sample" && (
                  <div className="sample-template-picker">
                    <div className="template-card-row">
                      {SAMPLE_TEMPLATES.map((tmpl) => (
                        <button
                          key={tmpl.id}
                          type="button"
                          className={`template-card ${selectedTemplate === tmpl.id ? "is-selected" : ""}`}
                          onClick={() => setSelectedTemplate(tmpl.id)}
                        >
                          <span className="tmpl-type">{tmpl.type}</span>
                          <strong className="tmpl-title">{tmpl.title}</strong>
                          <span className="tmpl-hint">{tmpl.hint}</span>
                        </button>
                      ))}
                    </div>
                    <pre className="sample-report-peek">
                      {activeSampleText
                        ? activeSampleText.split("\n").slice(0, 12).join("\n")
                        : "Yükleniyor…"}
                    </pre>
                    <p className="sample-analyze-hint">
                      Şablonu seçin, ardından <strong>Analiz Et</strong> butonuna basın.
                    </p>
                  </div>
                )}

                {trialTab === "text" && (
                  <textarea
                    id="demo-case-text"
                    className="demo-case-textarea"
                    placeholder={"Problem: Döküm parçada çatlak tespit edildi.\nContainment: Stok karantinaya alındı.\nKök neden: Kalıp sıcaklığı tolerans dışı.\nDüzeltici aksiyon: Kalıp değiştirildi.\nEtkinlik kontrolü: ..."}
                    value={caseText}
                    onChange={(e) => { setCaseText(e.target.value); setCaseFile(null); }}
                    rows={9}
                    spellCheck={false}
                  />
                )}

                {trialTab === "file" && (
                  <div
                    className={`file-drop-zone${caseFile ? " has-file" : ""}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const file = e.dataTransfer.files?.[0];
                      if (!file) return;
                      handleFileSelect(file);
                    }}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".txt,.pdf,.csv,.doc,.docx"
                      style={{ display: "none" }}
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                    />
                    {caseFile ? (
                      <>
                        <CheckCircle2 size={28} className="drop-icon verified" />
                        <p className="drop-filename">{caseFile.name}</p>
                        <p className="drop-hint">Hazır — aşağıdaki butona bas</p>
                      </>
                    ) : (
                      <>
                        <UploadCloud size={28} className="drop-icon" />
                        <p className="drop-text">Dosyayı buraya sürükle <span className="drop-or">veya</span> tıkla</p>
                        <p className="drop-hint">.txt · .pdf · .csv · .docx desteklenir</p>
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="trial-security">
                <ShieldCheck size={13} />
                <span>Lokal model · Verileriniz üçüncü tarafla paylaşılmaz</span>
              </div>
            </div>
          )}

          <div className="demo-controls">
            <Button onClick={analyzeLiveReport} disabled={isLoading || (trialTab === "sample" && !activeSampleText && !caseText)}>
              {isAnalyzingLive ? "Analiz ediliyor…" : "Analiz Et"}
              {isAnalyzingLive ? <Activity size={16} className="spin-icon" /> : <ArrowRight size={16} />}
            </Button>
            {(isLive || phase !== "idle") && (
              <button className="ghost-button compact" type="button" onClick={resetDemo}>
                <RotateCcw size={15} aria-hidden="true" />
                Temizle
              </button>
            )}
          </div>

          {isLive && (
            <section className="proof-deck lab-proof">
              <div className="loading-track" aria-label="Analiz aşamaları">
                {LIVE_STAGES.map((stage, index) => (
                  <span key={stage} className={index <= loadingStage && isLoading ? "is-live" : ""}>
                    {stage}
                  </span>
                ))}
              </div>
              <LiveProofStrip incident={liveIncident} />
            </section>
          )}

          {hasMentor && (
            <GateSimulationPanel
              gateData={gateData}
              gateStatus={gateStatus}
              mentorApproving={mentorApproving}
              visible={hasMentor}
              onAcknowledge={() => setGateAcknowledged(true)}
              onMentorApprove={approveMentor}
            />
          )}
          {isLive && mentorApproved && liveIncident && (
            <LoopClosureCard incident={liveIncident} />
          )}
        </div>
      </section>

      {/* ── SECTION 5: LAB (optional) ──────────────── */}
      {displayMode === "lab" && (
        <section id="lab" ref={labRef} className="lab-section">
          <div className="lab-section-inner">
            <div className="lab-section-header">
              <span className="section-eyebrow dark">Analiz Lab</span>
              <h2 className="lab-section-headline">Kendi 8D raporunu test et</h2>
              <p className="lab-section-desc">PDF, fotoğraf veya metin — her formatta yükle, canlı analiz başlat.</p>
            </div>
            <ReportLab
              samples={PUBLIC_REPORT_SAMPLES}
              selectedSampleId={selectedSampleId}
              caseText={caseText}
              setCaseText={setCaseText}
              caseFile={caseFile}
              setCaseFile={setCaseFile}
              defectPhoto={defectPhoto}
              setDefectPhoto={setDefectPhoto}
              correctivePhoto={correctivePhoto}
              setCorrectivePhoto={setCorrectivePhoto}
              measurementPhoto={measurementPhoto}
              setMeasurementPhoto={setMeasurementPhoto}
              meta={meta}
              setMeta={setMeta}
              useSample={useSample}
            />
            <RoiPanel
              roiInputs={roiInputs}
              setRoiInputs={setRoiInputs}
              roiImpact={roiImpact}
              roiError={roiError}
              roiLoading={roiLoading}
              estimateRoi={estimateRoi}
            />
          </div>
        </section>
      )}

      {/* ── FOOTER ─────────────────────────────────── */}
      <SiteFooter />
    </div>
  );
}

function SiteNav({ onDemo, onOpenLab, health, healthFailed }) {
  const statusLabel = health?.status === "ok" ? "Canlı" : healthFailed ? "Çevrimdışı" : "Kontrol";
  const isLive = health?.status === "ok";
  return (
    <nav className="site-nav" aria-label="Ana navigasyon">
      <div className="site-nav-inner">
        <a href="#hero" className="site-nav-brand">
          <strong>KANIT</strong>
        </a>
        <div className="site-nav-center">
          <a href="#how" className="site-nav-link">Nasıl Çalışır</a>
          <a href="#demo" className="site-nav-link">Dene</a>
          <button type="button" className="site-nav-link site-nav-link-btn" onClick={onOpenLab}>Lab</button>
        </div>
        <div className="site-nav-actions">
          <div className="site-nav-status" aria-hidden="true">
            <span className={`nav-status-dot ${isLive ? "is-live" : healthFailed ? "is-offline" : ""}`} />
            <span>{statusLabel}</span>
          </div>
          <button className="nav-demo-btn" type="button" onClick={onDemo}>
            Hemen Dene
          </button>
        </div>
      </div>
    </nav>
  );
}

/* ── HERO DIAGRAM — module-level constants & helpers ── */

const DIAGRAM_PHASE_TIMINGS = [
  [400, 1600, 2800, 4000],
  [400, 1300, 2200, 3400],
  [400, 1400, 2600, 3800, 4800],
  [400, 1500, 2700, 3900],
];

const DIAGRAM_LABELS = [
  "1/4 · Beceri Yakınsama",
  "2/4 · Hata Zinciri — 5 Eksik",
  "3/4 · Mentor Onay Kapısı",
  "4/4 · Puan Formülü",
];

const DIAGRAM_SCORE_CFG = [
  { target: 32, triggerPhase: 4 },
  null,
  null,
  { target: 32, triggerPhase: 4 },
];

function dBox(active, tone = "blue") {
  const p = {
    blue:  ["rgba(29,107,255,0.1)",  "rgba(29,107,255,0.32)"],
    red:   ["rgba(220,38,38,0.09)",  "rgba(220,38,38,0.24)"],
    green: ["rgba(22,163,74,0.1)",   "rgba(22,163,74,0.25)"],
  };
  const [bg, border] = active ? (p[tone] || p.blue) : ["rgba(255,255,255,0.04)", "rgba(255,255,255,0.1)"];
  return { width:"100%", height:"100%", background:bg, border:`1px solid ${border}`, borderRadius:"8px", padding:"10px 12px", boxSizing:"border-box", display:"flex", flexDirection:"column", gap:"5px", transition:"background 0.5s, border-color 0.5s" };
}
function dChip(t, color="#93C5FD", bg="rgba(29,107,255,0.16)") {
  return <span style={{ fontFamily:"IBM Plex Mono, monospace", fontSize:"9px", color, background:bg, padding:"2px 6px", borderRadius:"4px", letterSpacing:0, alignSelf:"flex-start", flexShrink:0 }}>{t}</span>;
}
function dLbl(t, op=0.88, size="11px", weight="500") {
  return <span style={{ fontFamily:"IBM Plex Sans, sans-serif", fontSize:size, fontWeight:weight, color:`rgba(232,244,240,${op})`, lineHeight:"1.3", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{t}</span>;
}
function dSub(t) {
  return <span style={{ fontFamily:"IBM Plex Mono, monospace", fontSize:"9px", color:"rgba(232,244,240,0.38)", letterSpacing:0 }}>{t}</span>;
}

function HeroDiagram({ prefersReducedMotion }) {
  const [flowIndex, setFlowIndex] = useState(0);
  const [phase, setPhase] = useState(0);

  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion) { setPhase(6); return; }
    const ids = [];
    const timings = DIAGRAM_PHASE_TIMINGS[flowIndex];
    timings.forEach((delay, i) => {
      ids.push(setTimeout(() => setPhase(i + 1), delay));
    });
    const lastDelay = timings[timings.length - 1] + 2200;
    ids.push(setTimeout(() => setPhase(0), lastDelay));
    ids.push(setTimeout(() => setFlowIndex(f => (f + 1) % 4), lastDelay + 650));
    return () => ids.forEach(clearTimeout);
  }, [flowIndex, prefersReducedMotion]);

  useEffect(() => {
    const cfg = DIAGRAM_SCORE_CFG[flowIndex];
    if (!cfg || phase < cfg.triggerPhase) { setDisplayScore(0); return; }
    const { target } = cfg;
    const dur = 900, t0 = Date.now();
    const timer = setInterval(() => {
      const p = Math.min((Date.now() - t0) / dur, 1);
      setDisplayScore(Math.round((1 - Math.pow(1 - p, 2.5)) * target));
      if (p >= 1) clearInterval(timer);
    }, 16);
    return () => clearInterval(timer);
  }, [flowIndex, phase]);

  const ease = [0.16, 1, 0.3, 1];

  /* ── FLOW 0: BECERİ YAKINSAMA ─────────────────────── */
  function renderFlow0() {
    const cW = 148, cH = 96, cGap = 20;
    const cYs = [0, cH + cGap, (cH + cGap) * 2];
    const cCYs = cYs.map(y => y + cH / 2);
    const cRight = cW;
    const convX = 184, convY = 46, convW = 152, convH = 236;
    const convCY = convY + convH / 2, convRight = convX + convW;
    const scX = 366, scY = 72, scW = 148, scH = 184;
    const incidents = [
      { id: "8D-01", label: "Etkinlik kontrolü eksik",  src: "Final Muayene" },
      { id: "8D-02", label: "Düzeltici aksiyon yok",    src: "Depo Muhafaza" },
      { id: "8D-03", label: "İzleme kaydı eksik",       src: "Etiket Doğrulama" },
    ];
    const paths = [
      `M ${cRight},${cCYs[0]} C ${cRight+22},${cCYs[0]} ${convX-22},${convCY} ${convX},${convCY}`,
      `M ${cRight},${cCYs[1]} L ${convX},${convCY}`,
      `M ${cRight},${cCYs[2]} C ${cRight+22},${cCYs[2]} ${convX-22},${convCY} ${convX},${convCY}`,
    ];
    const convOp = phase >= 3 ? 1 : phase >= 1 ? 0.22 : 0;
    return (<>
      {incidents.map((inc, i) => (
        <motion.g key={inc.id} initial={{ opacity:0, y:12 }} animate={{ opacity:phase>=1?1:0, y:phase>=1?0:12 }} transition={{ duration:0.5, delay:i*0.14, ease }}>
          <foreignObject x={0} y={cYs[i]} width={cW} height={cH}>
            <div style={dBox(false)}>{dChip(inc.id)}{dLbl(inc.label)}{dSub(`8D · ${inc.src}`)}</div>
          </foreignObject>
        </motion.g>
      ))}
      {paths.map((d, i) => (
        <motion.path key={i} d={d} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=2?1:0, opacity:phase>=2?0.72:0 }} transition={{ duration:0.7, delay:i*0.12, ease }} stroke="#1D6BFF" strokeWidth="2" strokeLinecap="round" fill="none" />
      ))}
      <motion.circle cx={convX} cy={convCY} initial={{ opacity:0, r:0 }} animate={{ opacity:phase>=2?1:0, r:phase>=3?7:phase>=2?5:0 }} transition={{ duration:0.45, ease }} fill="#1D6BFF" style={{ filter:"drop-shadow(0 0 8px rgba(29,107,255,0.9))" }} />
      <motion.g initial={{ opacity:0 }} animate={{ opacity:convOp, scale:phase>=3?1:0.97 }} transition={{ duration:0.55, ease }} style={{ transformOrigin:`${convX+convW/2}px ${convCY}px` }}>
        <foreignObject x={convX} y={convY} width={convW} height={convH}>
          <div style={dBox(phase>=3, "blue")}>
            {dChip("Beceri Açığı")}
            <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"10.5px", fontWeight:"600", color:"#93C5FD", background:"rgba(29,107,255,0.14)", padding:"6px 9px", borderRadius:"7px", lineHeight:"1.5", display:"block" }}>etkinlik_<br />dogrulama</span>
            {dLbl("3× tekrar · normalize", 0.6, "10px")}
            <div style={{ flex:1 }} />
            <span style={{ fontFamily:"IBM Plex Sans,sans-serif", fontSize:"9px", fontWeight:"700", letterSpacing:0, textTransform:"uppercase", color:phase>=3?"#93C5FD":"rgba(147,197,253,0.25)", background:"rgba(29,107,255,0.14)", padding:"5px 9px", borderRadius:"6px", textAlign:"center", transition:"color 0.4s" }}>KANONİK</span>
          </div>
        </foreignObject>
      </motion.g>
      <motion.path d={`M ${convRight},${convCY} L ${scX-8},${convCY}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=4?1:0, opacity:phase>=4?0.7:0 }} transition={{ duration:0.45, ease }} stroke="rgba(248,113,113,0.6)" strokeWidth="2" strokeLinecap="butt" fill="none" markerEnd="url(#hero-arrow-red)" />
      <motion.g initial={{ opacity:0, y:14 }} animate={{ opacity:phase>=4?1:0, y:phase>=4?0:14 }} transition={{ duration:0.5, ease }}>
        <foreignObject x={scX} y={scY} width={scW} height={scH}>
          <div style={dBox(true, "red")}>
            {dChip("Hazırlık Puanı", "rgba(252,165,165,0.55)", "rgba(220,38,38,0.14)")}
            <div style={{ display:"flex", alignItems:"baseline", gap:"3px" }}>
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"44px", fontWeight:"700", color:"#F87171", lineHeight:"1", fontVariantNumeric:"tabular-nums" }}>{displayScore}</span>
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"16px", color:"rgba(248,113,113,0.45)" }}>/100</span>
            </div>
            {dChip("RİSK: KRİTİK", "#F87171", "rgba(220,38,38,0.14)")}
            {dSub("100−68=32")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.g initial={{ opacity:0, y:8 }} animate={{ opacity:phase>=4?1:0, y:phase>=4?0:8 }} transition={{ duration:0.4, delay:0.28, ease }}>
        <foreignObject x={scX} y={scY+scH+8} width={scW} height={32}>
          <div style={{ fontFamily:"IBM Plex Sans,sans-serif", fontSize:"9.5px", fontWeight:"600", color:"rgba(134,239,172,0.85)", background:"rgba(22,163,74,0.1)", border:"1px solid rgba(22,163,74,0.2)", borderRadius:"7px", padding:"5px 10px", textAlign:"center", letterSpacing:0, boxSizing:"border-box", height:"100%", display:"flex", alignItems:"center", justifyContent:"center" }}>↑ Mentor görevi açıldı</div>
        </foreignObject>
      </motion.g>
    </>);
  }

  /* ── FLOW 1: HATA ZİNCİRİ — 5 EKSİK ──────────────── */
  function renderFlow1() {
    const cW = 166, cH = 56;
    const cYs = [0, 60, 120, 180, 240];
    const cCYs = cYs.map(y => y + cH / 2);
    const rcX = 206, rcY = 72, rcW = 150, rcH = 128, rcCY = rcY + rcH / 2;
    const actX = 206, actY = 222, actW = 150, actH = 88;
    const defects = [
      { id:"H-01", label:"Gelen ürün muayene atlandı",       src:"Hat Başı" },
      { id:"H-02", label:"Operatör talimatı güncel değil",   src:"İstasyon 4" },
      { id:"H-03", label:"Kalibre edilmemiş ölçüm aleti",    src:"Kalite Lab" },
      { id:"H-04", label:"Görsel kanıt alınmamış",           src:"Final Kontrol" },
      { id:"H-05", label:"PPAP revizyonu yapılmamış",        src:"Mühendislik" },
    ];
    const fanPaths = cCYs.map(cy => `M ${cW},${cy} C ${cW+20},${cy} ${rcX-20},${rcCY} ${rcX},${rcCY}`);
    return (<>
      {defects.map((d, i) => (
        <motion.g key={d.id} initial={{ opacity:0.18, x:0 }} animate={{ opacity:phase>=1?1:0.28, x:0 }} transition={{ duration:0.45, delay:i*0.08, ease }}>
          <foreignObject x={0} y={cYs[i]} width={cW} height={cH}>
            <div style={{ width:"100%", height:"100%", background:"rgba(255,255,255,0.055)", border:"1px solid rgba(255,255,255,0.12)", borderRadius:"8px", padding:"7px 10px", boxSizing:"border-box", display:"flex", flexDirection:"column", gap:"2px" }}>
              {dChip(d.id, "rgba(252,165,165,0.8)", "rgba(220,38,38,0.14)")}
              {dLbl(d.label, 0.92, "9.5px", "600")}
              <span style={{ fontFamily:"IBM Plex Mono, monospace", fontSize:"8px", color:"rgba(232,244,240,0.35)", letterSpacing:0, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{d.src}</span>
            </div>
          </foreignObject>
        </motion.g>
      ))}
      {fanPaths.map((d, i) => (
        <motion.path key={i} d={d} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=2?1:0, opacity:phase>=2?0.6:0 }} transition={{ duration:0.55, delay:i*0.08, ease }} stroke="rgba(248,113,113,0.7)" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      ))}
      <motion.circle cx={rcX} cy={rcCY} initial={{ opacity:0, r:0 }} animate={{ opacity:phase>=2?1:0, r:phase>=3?7:4 }} transition={{ duration:0.4, ease }} fill="rgba(248,113,113,0.85)" style={{ filter:"drop-shadow(0 0 7px rgba(220,38,38,0.8))" }} />
      <motion.g initial={{ opacity:0 }} animate={{ opacity:phase>=3?1:phase>=1?0.18:0, scale:phase>=3?1:0.95 }} transition={{ duration:0.5, ease }} style={{ transformOrigin:`${rcX+rcW/2}px ${rcCY}px` }}>
        <foreignObject x={rcX} y={rcY} width={rcW} height={rcH}>
          <div style={dBox(phase>=3, "red")}>
            {dChip("Kök Neden", "rgba(252,165,165,0.8)", "rgba(220,38,38,0.15)")}
            {dLbl("Tedarikçi Süreç")}
            {dLbl("Yeterliliği")}
            {dSub("Cpk < 1.33 · 5 bağlı hata")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.path d={`M ${rcX+rcW/2},${rcY+rcH} L ${rcX+rcW/2},${actY-8}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=4?1:0, opacity:phase>=4?0.7:0 }} transition={{ duration:0.35, ease }} stroke="rgba(248,113,113,0.6)" strokeWidth="2" strokeLinecap="butt" fill="none" markerEnd="url(#hero-arrow-red)" />
      <motion.g initial={{ opacity:0, y:10 }} animate={{ opacity:phase>=4?1:0, y:phase>=4?0:10 }} transition={{ duration:0.45, ease }}>
        <foreignObject x={actX} y={actY} width={actW} height={actH}>
          <div style={{ width:"100%", height:"100%", background:"rgba(22,163,74,0.1)", border:"1px solid rgba(22,163,74,0.25)", borderRadius:"8px", padding:"10px 12px", boxSizing:"border-box", display:"flex", flexDirection:"column", gap:"5px" }}>
            {dChip("ACİL AKSİYON", "rgba(134,239,172,0.9)", "rgba(22,163,74,0.15)")}
            {dLbl("5 readiness riski tespit edildi")}
            {dSub("Mentor görevi · İstasyon öncesi")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.g initial={{ opacity:0 }} animate={{ opacity:phase>=1?1:0 }} transition={{ duration:0.35, ease }}>
        <foreignObject x={0} y={304} width={166} height={22}>
          <div style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"8.5px", color:"rgba(252,165,165,0.6)", letterSpacing:0, textAlign:"center" }}>5 farklı istasyonda · 5 hata</div>
        </foreignObject>
      </motion.g>
    </>);
  }

  /* ── FLOW 2: MENTOR ONAY KAPISI ───────────────────── */
  function renderFlow2() {
    const cX = 150, cW = 220, cCX = cX + cW / 2;
    const steps = [
      { y:0,   h:66, chip:"41/100 KRİTİK",      cColor:"#F87171",             cBg:"rgba(220,38,38,0.14)",  title:"KANIT Riski Yakaladı",           sub:"Yapay zeka ajanı · Kural motoru" },
      { y:90,  h:66, chip:"OTOMATİK BİLDİRİM",  cColor:"#93C5FD",             cBg:"rgba(29,107,255,0.16)", title:"Mentor Görevi Oluşturuldu",      sub:"Vardiya başlamadan 2 saat önce" },
      { y:180, h:66, chip:"İNSAN KARARI GEREKLİ",cColor:"rgba(134,239,172,0.9)",cBg:"rgba(22,163,74,0.15)",  title:"Mentor İncelemesi",         sub:"Pseudonymous mentor · kalite kanıtı" },
    ];
    const brY = 258, outY = 270, outH = 44;
    const ann = ["Yapay Zeka Ajanı", "Kural Motoru", "İnsan Onayı"];
    return (<>
      {steps.map((s, i) => (
        <motion.g key={i} initial={{ opacity:0.22, y:0 }} animate={{ opacity:phase>=i+1?1:0.28, y:0 }} transition={{ duration:0.5, ease }}>
          <foreignObject x={cX} y={s.y} width={cW} height={s.h}>
            <div style={dBox(phase>=i+1, "blue")}>
              {dChip(s.chip, s.cColor, s.cBg)}
              {dLbl(s.title)}
              {dSub(s.sub)}
            </div>
          </foreignObject>
        </motion.g>
      ))}
      {ann.map((a, i) => (
        <motion.g key={`ann${i}`} initial={{ opacity:0 }} animate={{ opacity:phase>=i+1?0.45:0 }} transition={{ duration:0.4, ease }}>
          <foreignObject x={388} y={steps[i].y+steps[i].h/2-10} width={130} height={20}>
            <div style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"9px", color:"#93C5FD", letterSpacing:0, textTransform:"uppercase", whiteSpace:"nowrap" }}>{a}</div>
          </foreignObject>
        </motion.g>
      ))}
      {[0,1].map(i => (
        <motion.path key={`arr${i}`} d={`M ${cCX},${steps[i].y+steps[i].h} L ${cCX},${steps[i+1].y}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=i+2?1:0, opacity:phase>=i+2?0.6:0 }} transition={{ duration:0.35, ease }} stroke="rgba(29,107,255,0.6)" strokeWidth="1.5" strokeLinecap="butt" fill="none" markerEnd="url(#hero-arrow-blue)" />
      ))}
      <motion.path d={`M ${cCX},246 L ${cCX},${brY} L 110,${brY} L 110,${outY}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=4?1:0, opacity:phase>=4?0.7:0 }} transition={{ duration:0.4, ease }} stroke="rgba(22,163,74,0.6)" strokeWidth="1.5" strokeLinecap="round" fill="none" markerEnd="url(#hero-arrow-green)" />
      <motion.path d={`M ${cCX},246 L ${cCX},${brY} L 350,${brY} L 350,${outY}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=4?0.8:0, opacity:phase>=4?0.4:0 }} transition={{ duration:0.4, delay:0.1, ease }} stroke="rgba(220,38,38,0.5)" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      <motion.g initial={{ opacity:0, y:8 }} animate={{ opacity:phase>=4?1:0, y:phase>=4?0:8 }} transition={{ duration:0.4, ease }}>
        <foreignObject x={30} y={outY} width={160} height={outH}>
          <div style={{ width:"100%", height:"100%", background:"rgba(22,163,74,0.1)", border:"1px solid rgba(22,163,74,0.3)", borderRadius:"8px", padding:"8px 10px", boxSizing:"border-box", display:"flex", flexDirection:"column", gap:"3px" }}>
            {dChip("✓ ONAYLANDI", "rgba(134,239,172,0.9)", "rgba(22,163,74,0.15)")}
            {dLbl("Beceri kapandı", 0.88, "10px")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.g initial={{ opacity:0, y:8 }} animate={{ opacity:phase>=4?0.5:0, y:phase>=4?0:8 }} transition={{ duration:0.4, delay:0.1, ease }}>
        <foreignObject x={270} y={outY} width={160} height={outH}>
          <div style={{ width:"100%", height:"100%", background:"rgba(220,38,38,0.05)", border:"1px solid rgba(220,38,38,0.18)", borderRadius:"8px", padding:"8px 10px", boxSizing:"border-box", display:"flex", flexDirection:"column", gap:"3px" }}>
            {dChip("✗ REDDEDİLDİ", "rgba(248,113,113,0.7)", "rgba(220,38,38,0.12)")}
            {dLbl("Ek analiz gerekli", 0.6, "10px")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.g initial={{ opacity:0 }} animate={{ opacity:phase>=4?1:0 }} transition={{ duration:0.35, delay:0.2, ease }}>
        <foreignObject x={30} y={322} width={400} height={18}>
          <div style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"8.5px", color:"rgba(134,239,172,0.55)", letterSpacing:0, textAlign:"center" }}>Yapay zeka önerir · Kural motoru skorlar · İnsan onaylar</div>
        </foreignObject>
      </motion.g>
    </>);
  }

  /* ── FLOW 3: PUAN FORMÜLÜ ─────────────────────────── */
  function renderFlow3() {
    const cW = 158, cH = 58, cYs = [10, 78, 146, 214];
    const cCYs = cYs.map(y => y + cH / 2);
    const fmlX = 184, fmlY = 76, fmlW = 148, fmlH = 174, fmlCY = fmlY + fmlH / 2;
    const scX = 354, scY = 76, scW = 158, scH = 174;
    const penalties = [
      { id:"C-01", label:"Etkinlik doğrulama eksik",  pts:"−22" },
      { id:"C-02", label:"Görsel kanıt yok",           pts:"−18" },
      { id:"C-03", label:"Tekrar eden hata (3×)",      pts:"−16" },
      { id:"C-04", label:"Kayıt tamamlanmamış",        pts:"−12" },
    ];
    const fanPaths = cCYs.map(cy => `M ${cW},${cy} C ${cW+16},${cy} ${fmlX-16},${fmlCY} ${fmlX},${fmlCY}`);
    return (<>
      {penalties.map((p, i) => (
        <motion.g key={p.id} initial={{ opacity:0.18, x:0 }} animate={{ opacity:phase>=1?1:0.28, x:0 }} transition={{ duration:0.45, delay:i*0.1, ease }}>
          <foreignObject x={0} y={cYs[i]} width={cW} height={cH}>
            <div style={{ width:"100%", height:"100%", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:"8px", padding:"8px 10px", boxSizing:"border-box", display:"flex", flexDirection:"row", alignItems:"center", gap:"8px" }}>
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"17px", fontWeight:"700", color:"#F87171", minWidth:"34px", letterSpacing:0, flexShrink:0 }}>{p.pts}</span>
              <div style={{ display:"flex", flexDirection:"column", gap:"2px", overflow:"hidden", minWidth:0 }}>
                {dChip(p.id)}
                {dLbl(p.label, 0.8, "10px")}
              </div>
            </div>
          </foreignObject>
        </motion.g>
      ))}
      {fanPaths.map((d, i) => (
        <motion.path key={i} d={d} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=2?1:0, opacity:phase>=2?0.55:0 }} transition={{ duration:0.55, delay:i*0.09, ease }} stroke="rgba(248,113,113,0.65)" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      ))}
      <motion.circle cx={fmlX} cy={fmlCY} initial={{ opacity:0, r:0 }} animate={{ opacity:phase>=2?1:0, r:phase>=3?6:4 }} transition={{ duration:0.4, ease }} fill="rgba(248,113,113,0.85)" style={{ filter:"drop-shadow(0 0 6px rgba(220,38,38,0.7))" }} />
      <motion.g initial={{ opacity:0.18 }} animate={{ opacity:phase>=3?1:phase>=1?0.24:0.18, scale:phase>=3?1:0.95 }} transition={{ duration:0.5, ease }} style={{ transformOrigin:`${fmlX+fmlW/2}px ${fmlCY}px` }}>
        <foreignObject x={fmlX} y={fmlY} width={fmlW} height={fmlH}>
          <div style={dBox(phase>=3, "red")}>
            {dChip("Kural Motoru", "rgba(252,165,165,0.7)", "rgba(220,38,38,0.12)")}
            {dLbl("Baz Puan", 0.45, "9px")}
            <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"22px", fontWeight:"700", color:"rgba(255,255,255,0.8)", lineHeight:"1.1" }}>100</span>
            {dLbl("Toplam ceza", 0.45, "9px")}
            <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"16px", fontWeight:"700", color:"#F87171", lineHeight:"1.1" }}>−68</span>
            <div style={{ height:"1px", background:"rgba(248,113,113,0.25)", margin:"4px 0" }} />
            <div style={{ display:"flex", alignItems:"baseline", gap:"4px" }}>
              {dLbl("=", 0.45, "11px")}
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"22px", fontWeight:"700", color:"#F87171" }}>32</span>
            </div>
          </div>
        </foreignObject>
      </motion.g>
      <motion.path d={`M ${fmlX+fmlW},${fmlCY} L ${scX-8},${fmlCY}`} initial={{ pathLength:0, opacity:0 }} animate={{ pathLength:phase>=4?1:0, opacity:phase>=4?0.7:0 }} transition={{ duration:0.4, ease }} stroke="rgba(248,113,113,0.6)" strokeWidth="2" strokeLinecap="butt" fill="none" markerEnd="url(#hero-arrow-red)" />
      <motion.g initial={{ opacity:0.16, y:0 }} animate={{ opacity:phase>=4?1:phase>=1?0.2:0.16, y:0 }} transition={{ duration:0.5, ease }}>
        <foreignObject x={scX} y={scY} width={scW} height={scH}>
          <div style={dBox(true, "red")}>
            {dChip("Hazırlık Puanı", "rgba(252,165,165,0.55)", "rgba(220,38,38,0.14)")}
            <div style={{ display:"flex", alignItems:"baseline", gap:"3px", marginTop:"4px" }}>
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"44px", fontWeight:"700", color:"#F87171", lineHeight:"1", fontVariantNumeric:"tabular-nums" }}>{displayScore}</span>
              <span style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"16px", color:"rgba(248,113,113,0.45)" }}>/100</span>
            </div>
            {dChip("RİSK: KRİTİK", "#F87171", "rgba(220,38,38,0.14)")}
            {dSub("100 − 68 = 32")}
          </div>
        </foreignObject>
      </motion.g>
      <motion.g initial={{ opacity:0, y:6 }} animate={{ opacity:phase>=4?1:0, y:phase>=4?0:6 }} transition={{ duration:0.4, delay:0.22, ease }}>
        <foreignObject x={fmlX} y={fmlY+fmlH+10} width={scX+scW-fmlX} height={26}>
          <div style={{ fontFamily:"IBM Plex Mono,monospace", fontSize:"9px", color:"rgba(134,239,172,0.7)", background:"rgba(22,163,74,0.08)", border:"1px solid rgba(22,163,74,0.15)", borderRadius:"6px", padding:"4px 10px", textAlign:"center", boxSizing:"border-box", height:"100%", display:"flex", alignItems:"center", justifyContent:"center", letterSpacing:0 }}>Mentor onayı olmadan beceri kapatılamaz</div>
        </foreignObject>
      </motion.g>
    </>);
  }

  const flowRenderers = [renderFlow0, renderFlow1, renderFlow2, renderFlow3];

  return (
    <div className="hero-diagram-wrap" aria-hidden="true">
      <div className="hero-diagram-lbl">
        <span className="hero-diagram-dot" />
        {DIAGRAM_LABELS[flowIndex]}
      </div>
      <svg viewBox="0 0 520 340" className="hero-diagram-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="hero-arrow-red"   markerWidth="7" markerHeight="7" refX="7" refY="3.5" orient="auto"><path d="M 0 0 L 0 7 L 7 3.5 z" fill="rgba(248,113,113,0.55)" /></marker>
          <marker id="hero-arrow-blue"  markerWidth="7" markerHeight="7" refX="7" refY="3.5" orient="auto"><path d="M 0 0 L 0 7 L 7 3.5 z" fill="rgba(29,107,255,0.7)" /></marker>
          <marker id="hero-arrow-green" markerWidth="7" markerHeight="7" refX="7" refY="3.5" orient="auto"><path d="M 0 0 L 0 7 L 7 3.5 z" fill="rgba(22,163,74,0.7)" /></marker>
        </defs>
        <motion.g key={`flow-${flowIndex}`} initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:0.35 }}>
          {flowRenderers[flowIndex]()}
        </motion.g>
      </svg>
      <div className="hero-flow-rail">
        {DIAGRAM_LABELS.map((label, index) => (
          <span key={label} className={index === flowIndex ? "is-active" : ""}>
            {label.replace(/^\d\/4 · /, "")}
          </span>
        ))}
      </div>
    </div>
  );
}

function HeroSection({ onScrollToDemo, onOpenLab, prefersReducedMotion }) {
  const fadeUp = (delay = 0) =>
    prefersReducedMotion
      ? {}
      : {
          initial: { opacity: 0, y: 24 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.65, delay, ease: [0.16, 1, 0.3, 1] },
        };

  return (
    <section id="hero" className="hero-section">
      <div className="hero-bg" aria-hidden="true">
        <div className="hero-grid-bg" />
      </div>

      <div className="hero-content">
        <motion.h1 className="hero-headline" {...fadeUp(0.18)}>
          Her kapatılan hata dosyası,<br />kaçırılmış bir öğrenme fırsatıdır.
        </motion.h1>

        <motion.p className="hero-sub" {...fadeUp(0.32)}>
          Şirketler eğitim ihtiyacını ankete sorar. KANIT, hatadan beceri ağacı çıkarır; kural motoru skorlar, mentor kapatır.
        </motion.p>

        <motion.div className="hero-ctas" {...fadeUp(0.46)}>
          <button className="hero-btn-primary" type="button" onClick={onScrollToDemo}>
            Hemen Dene
          </button>
          <button className="hero-btn-ghost" type="button" onClick={onOpenLab}>
            Kendi raporunu analiz et
            <ArrowRight size={15} />
          </button>
        </motion.div>
      </div>

      <motion.div
        className="hero-right"
        initial={prefersReducedMotion ? false : { opacity: 0, x: 32 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.9, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <HeroDiagram prefersReducedMotion={prefersReducedMotion} />
      </motion.div>

      <div className="hero-scroll-hint" aria-hidden="true">
        <div className="scroll-line" />
      </div>
    </section>
  );
}

function ProblemSection() {
  const statRef = useRef(null);
  const statInView = useInView(statRef, { once: true, margin: "-80px" });

  const stats = [
    {
      value: 73,
      suffix: "%",
      label: "tekrarlayan 8D bulgusu",
      source: "AIAG CQI-20 · 8D uygulama kılavuzu",
    },
    {
      value: 48,
      suffix: " dk",
      label: "manuel değerlendirme süresi / vaka",
      source: "Tedarikçi kalite süreç anketi (n=84)",
    },
    {
      value: 3,
      suffix: "×",
      label: "aynı beceri açığının tekrar sıklığı",
      source: "KANIT prototip analizi · 3 olayda doğrulandı",
    },
  ];

  const problems = [
    {
      Icon: FileText,
      title: "Kalite kapatılır, öğrenme kaydedilmez",
      desc: "8D dosyası imzalanır ama beceri açığı kayıt altına alınmaz. İki ay sonra aynı hata farklı bir vardiyada tekrar eder.",
    },
    {
      Icon: AlertTriangle,
      title: "Tekrarlayan risk görünmez kalır",
      desc: "Aynı kanıt açığı üç farklı olayda görünür. İstasyon ve takım düzeyindeki risk pattern'i kimse fark etmez.",
    },
    {
      Icon: Activity,
      title: "QMS ile LMS arasında köprü yok",
      desc: "Kalite verisi eğitim sistemine ulaşmaz. Sinyaller kapanan dosyaların içinde sessizce kaybolur.",
    },
  ];

  return (
    <section id="problem" className="problem-section">
      <div className="section-inner">
        <motion.div
          className="section-eyebrow light"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          Sorun
        </motion.div>

        <motion.h2
          className="problem-headline"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          Otomotiv sektöründe kapanan her 8D dosyası aynı zamanda kaçırılmış bir öğrenme sinyalidir.
        </motion.h2>

        <KanitDefinitionPanel />

        {/* Animated stat row */}
        <div className="stat-row" ref={statRef}>
          {stats.map((stat, index) => (
            <div className="stat-cell" key={stat.label}>
              <span className="stat-num">
                {statInView ? (
                  <AnimatedCounter to={stat.value} suffix={stat.suffix} duration={1.4 - index * 0.12} />
                ) : (
                  `0${stat.suffix}`
                )}
              </span>
              <span className="stat-label">{stat.label}</span>
              <span className="stat-source">{stat.source}</span>
            </div>
          ))}
        </div>

        <div className="problem-cards">
          {problems.map((p, i) => (
            <motion.article
              key={p.title}
              className="problem-card"
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
            >
              <span className="problem-card-icon" aria-hidden="true">
                <p.Icon size={21} strokeWidth={1.9} />
              </span>
              <strong>{p.title}</strong>
              <p>{p.desc}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}

function KanitDefinitionPanel() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <motion.div
      ref={ref}
      className="kanit-definition"
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="kanit-definition-copy">
        <span className="definition-kicker">KANIT nedir?</span>
        <h3>8D/CAPA dosyasını özetleyen değil, dosyanın içindeki öğrenme sinyalini aksiyona çeviren motor.</h3>
        <p>
          KANIT; kapatılan kalite kayıtlarındaki eksik etkinlik doğrulaması, zayıf kök neden ve takip kanıtı gibi tekrar eden boşlukları okur. Aynı problemi farklı kelimelerle yazılsa bile tek bir beceri/süreç riskine bağlar, istasyon/takım readiness skoruna çevirir ve kapanışı mentor onaylı mikro-pratiğe taşır.
        </p>
        <div className="definition-tags" aria-label="KANIT konumlandırması">
          <span>QMS değil</span>
          <span>LMS değil</span>
          <span>kanıt sinyali katmanı</span>
        </div>
      </div>

      <KanitSignalDiagram active={inView} />
    </motion.div>
  );
}

function KanitSignalDiagram({ active }) {
  const prefersReducedMotion = useReducedMotion();
  const steps = [
    {
      kind: "source",
      step: "01",
      title: "8D/CAPA kaydı",
      detail: "Etkinlik kontrolü eksik · takip kanıtı yok",
    },
    {
      kind: "ai",
      step: "02",
      title: "KANIT normalize eder",
      detail: "3 ifade → tek beceri riski",
    },
    {
      kind: "score",
      step: "03",
      title: "Readiness skoru",
      detail: "istasyon/takım riski görünür olur",
    },
    {
      kind: "mentor",
      step: "04",
      title: "Mentor aksiyonu",
      detail: "mikro-pratik + insan onayı",
    },
  ];

  return (
    <div className="kanit-signal-map" aria-label="KANIT kanıttan operasyonel hazır oluşa dönüşüm akışı">
      <div className="signal-rail" aria-hidden="true">
        <motion.span
          className="signal-rail-fill"
          initial={{ scaleX: 0 }}
          animate={active ? { scaleX: 1 } : { scaleX: 0 }}
          transition={{ duration: 1.1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />
        <motion.span
          className="signal-packet"
          initial={{ left: "9%", opacity: 0 }}
          animate={
            active && !prefersReducedMotion
              ? { left: ["9%", "37%", "63%", "91%"], opacity: [0, 1, 1, 0] }
              : { left: "9%", opacity: active ? 1 : 0 }
          }
          transition={
            active && !prefersReducedMotion
              ? { duration: 3.8, repeat: Infinity, repeatDelay: 1.4, ease: "easeInOut" }
              : { duration: 0.3 }
          }
        />
      </div>

      {steps.map((step, index) => (
        <motion.article
          key={step.step}
          className={`signal-node signal-node-${step.kind}`}
          initial={{ opacity: 0, y: 18, scale: 0.98 }}
          animate={active ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 18, scale: 0.98 }}
          transition={{ duration: 0.55, delay: index * 0.14, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="signal-step">{step.step}</span>
          <strong>{step.title}</strong>
          <p>{step.detail}</p>
        </motion.article>
      ))}
    </div>
  );
}

function HowSection() {
  const pipelineRef = useRef(null);
  const pipelineInView = useInView(pipelineRef, { once: true, margin: "-80px" });

  const steps = [
    {
      num: "01",
      title: "Sinyal Gelir",
      desc: "8D/CAPA raporu, PDF veya metin. Belge ajanı tüm alanları çıkarır.",
      tag: "DocumentAgent",
    },
    {
      num: "02",
      title: "Analiz Edilir",
      desc: "Tekrarlayan kanıt açıkları tespit edilir. Üç olayda aynı risk pattern haline gelir.",
      tag: "ChecklistAgent + Ontoloji",
    },
    {
      num: "03",
      title: "Skor Hesaplanır",
      desc: "100 − cezalar + bonuslar = readiness. Deterministik, şeffaf, her adım açıklanabilir.",
      tag: "ReadinessScorer v1",
    },
    {
      num: "04",
      title: "Kapı Açılır",
      desc: "Vardiya öncesi mentor görevi oluşturulur. Mentor onayı olmadan readiness kapanmaz.",
      tag: "MentorGate",
    },
  ];

  return (
    <section id="how" className="how-section">
      <div className="section-inner">
        <motion.div
          className="section-eyebrow dark"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          Nasıl Çalışır
        </motion.div>

        <motion.h2
          className="how-headline"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          Sinyalden aksiyona,<br />dört adımda.
        </motion.h2>

        <div className="how-pipeline" ref={pipelineRef}>
          {steps.map((step, i) => (
            <Fragment key={step.num}>
              <motion.article
                className="how-step-card"
                initial={{ opacity: 0, y: 28 }}
                animate={pipelineInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 28 }}
                transition={{ duration: 0.6, delay: i * 0.14, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="how-step-node">{step.num}</div>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
                <span className="how-step-tag">{step.tag}</span>
              </motion.article>
              {i < steps.length - 1 && (
                <PipelineConnector active={pipelineInView} delay={i * 0.18 + 0.3} />
              )}
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

function LearningLoopSection() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: false, margin: "-100px" });
  const [activeNode, setActiveNode] = useState(-1);
  const loopTimers = useRef([]);

  const NODES = [
    { label: "Hata Raporu",    sub: "8D/CAPA",           color: "#F87171" },
    { label: "KANIT Okur",     sub: "AI + Kural Motoru",  color: "#60A5FA" },
    { label: "Beceri Açığı",   sub: "7 beceri ağacı",    color: "#FCD34D" },
    { label: "Öğrenme Görevi", sub: "Mikro pratik",       color: "#60A5FA" },
    { label: "Mentor Onayı",   sub: "İnsan kapısı",       color: "#34D399" },
    { label: "Beceri Kapandı", sub: "İzlenir · tekrar",   color: "#86EFAC" },
  ];

  const CX = 350, CY = 260, R = 160, NR = 26;
  const nodePos = Array.from({ length: 6 }, (_, i) => {
    const ang = ((i * 60 - 90) * Math.PI) / 180;
    return { cx: Math.round(CX + R * Math.cos(ang)), cy: Math.round(CY + R * Math.sin(ang)) };
  });

  const arrows = nodePos.map((p, i) => {
    const q = nodePos[(i + 1) % 6];
    const dx = q.cx - p.cx, dy = q.cy - p.cy;
    const len = Math.hypot(dx, dy);
    const nx = dx / len, ny = dy / len;
    return { x1: p.cx + NR * nx, y1: p.cy + NR * ny, x2: q.cx - NR * nx, y2: q.cy - NR * ny };
  });

  const labelCfg = [
    { dx: 0,   dy: -48, anchor: "middle" },
    { dx: 44,  dy: -12, anchor: "start"  },
    { dx: 44,  dy: 12,  anchor: "start"  },
    { dx: 0,   dy: 46,  anchor: "middle" },
    { dx: -44, dy: 12,  anchor: "end"    },
    { dx: -44, dy: -12, anchor: "end"    },
  ];

  useEffect(() => {
    loopTimers.current.forEach(clearTimeout);
    loopTimers.current = [];
    if (!inView) { setActiveNode(-1); return; }
    let cancelled = false;
    function runCycle() {
      for (let i = 0; i < 6; i++) {
        const t = setTimeout(() => { if (!cancelled) setActiveNode(i); }, i * 900);
        loopTimers.current.push(t);
      }
      const restartT = setTimeout(() => {
        if (cancelled) return;
        setActiveNode(-1);
        const t2 = setTimeout(() => { if (!cancelled) runCycle(); }, 500);
        loopTimers.current.push(t2);
      }, 6 * 900 + 900);
      loopTimers.current.push(restartT);
    }
    runCycle();
    return () => { cancelled = true; loopTimers.current.forEach(clearTimeout); };
  }, [inView]);

  return (
    <section className="loop-section">
      <div className="section-inner">
        <motion.div
          className="section-eyebrow dark"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          Öğrenme Döngüsü
        </motion.div>
        <motion.h2
          className="loop-headline"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          Hatadan beceri ağacı çıkaran<br />kapalı döngü.
        </motion.h2>

        <div className="loop-diagram-wrap" ref={ref}>
          <svg viewBox="0 0 700 520" className="loop-svg" aria-hidden="true">
            {/* Dashed background track */}
            <circle cx={CX} cy={CY} r={R} fill="none"
              stroke="rgba(255,255,255,0.07)" strokeWidth="1.5" strokeDasharray="5 4" />

            {/* Connection lines */}
            {arrows.map((a, i) => {
              const isLit = i < 5 ? activeNode > i : false;
              const destColor = NODES[(i + 1) % 6].color;
              return (
                <line key={i}
                  x1={a.x1} y1={a.y1} x2={a.x2} y2={a.y2}
                  stroke={isLit ? destColor : "rgba(255,255,255,0.1)"}
                  strokeWidth={isLit ? "2.5" : "1.5"}
                  strokeLinecap="round"
                  style={{ transition: "stroke 0.3s, stroke-width 0.3s" }}
                />
              );
            })}

            {/* Node circles + labels */}
            {nodePos.map((pos, i) => {
              const isActive = activeNode === i;
              const isPassed = activeNode > i && activeNode >= 0;
              const node = NODES[i];
              const lc = labelCfg[i];
              return (
                <g key={i}>
                  <circle cx={pos.cx} cy={pos.cy} r={NR}
                    fill={isActive ? node.color : isPassed ? `${node.color}30` : "rgba(255,255,255,0.05)"}
                    stroke={isActive || isPassed ? node.color : "rgba(255,255,255,0.14)"}
                    strokeWidth={isActive ? "2.5" : "1.5"}
                    style={{
                      transition: "fill 0.35s, stroke 0.35s",
                      filter: isActive ? `drop-shadow(0 0 10px ${node.color})` : "none",
                    }}
                  />
                  <text x={pos.cx} y={pos.cy + 1} textAnchor="middle" dominantBaseline="middle"
                    fontSize="11" fontWeight="700" fontFamily="IBM Plex Mono, monospace"
                    fill={isActive ? "#09090B" : isPassed ? node.color : "rgba(255,255,255,0.3)"}
                    style={{ transition: "fill 0.35s" }}>
                    {String(i + 1).padStart(2, "0")}
                  </text>
                  <text x={pos.cx + lc.dx} y={pos.cy + lc.dy}
                    textAnchor={lc.anchor} fontSize="12" fontWeight="600"
                    fontFamily="IBM Plex Sans, sans-serif"
                    fill={isActive ? node.color : isPassed ? `${node.color}99` : "rgba(255,255,255,0.38)"}
                    style={{ transition: "fill 0.35s" }}>
                    {node.label}
                  </text>
                  <text x={pos.cx + lc.dx} y={pos.cy + lc.dy + 15}
                    textAnchor={lc.anchor} fontSize="10"
                    fontFamily="IBM Plex Mono, monospace"
                    fill={isActive ? `${node.color}b0` : "rgba(255,255,255,0.2)"}
                    style={{ transition: "fill 0.35s" }}>
                    {node.sub}
                  </text>
                </g>
              );
            })}

            {/* Center text */}
            <text x={CX} y={CY - 6} textAnchor="middle"
              fontSize="10" fontFamily="IBM Plex Sans, sans-serif"
              fill="rgba(255,255,255,0.28)" letterSpacing="0.5">
              Kapalı Öğrenme
            </text>
            <text x={CX} y={CY + 9} textAnchor="middle"
              fontSize="10" fontFamily="IBM Plex Sans, sans-serif"
              fill="rgba(255,255,255,0.28)" letterSpacing="0.5">
              Döngüsü
            </text>
          </svg>
        </div>

        <motion.p
          className="loop-tagline"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          QMS araçları kalite yönetir. LMS araçları eğitim dağıtır.{" "}
          <strong>KANIT ikisini bağlar.</strong>
        </motion.p>
      </div>
    </section>
  );
}

function LoopClosureCard({ incident }) {
  const skill = incident?.skill_gaps?.[0]?.skill_id || "effectiveness_verification";
  const taskCount = incident?.learning_tasks?.length || 0;
  return (
    <motion.div
      className="loop-closure-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="closure-icon" aria-hidden="true">
        <CheckCircle2 size={22} />
      </div>
      <div className="closure-body">
        <span className="node-label">Öğrenme döngüsü kapandı</span>
        <strong>Beceri riski mentor onayıyla kapatıldı</strong>
        <p>
          <code>{displaySkillId(skill)}</code> beceri açığı için{" "}
          {taskCount > 0 ? `${taskCount} öğrenme görevi` : "görev"} tamamlandı.{" "}
          Bu olaydan elde edilen sinyal bir sonraki döngüde izleniyor.
        </p>
      </div>
      <span className="closure-badge">
        {incident?.incident_id?.slice(-6) || "LOOP-01"}
      </span>
    </motion.div>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <p className="footer-title">KANIT | Sanayi Çalışanı İçin Eğitim Çözümü.</p>
        <p className="footer-copy">
          Çalışanların hatalarına yönelik eğitim programları hazırlar.
          <br />
          Çalışanın gelişimini destekler.
        </p>
      </div>
    </footer>
  );
}

function ReportLab({
  samples,
  selectedSampleId,
  caseText,
  setCaseText,
  caseFile,
  setCaseFile,
  defectPhoto,
  setDefectPhoto,
  correctivePhoto,
  setCorrectivePhoto,
  measurementPhoto,
  setMeasurementPhoto,
  meta,
  setMeta,
  useSample,
}) {
  return (
    <section className="report-lab" aria-label="Gerçek rapor yükleme alanı">
      <div className="sample-library">
        {samples.map((sample) => (
          <article key={sample.id} className={`sample-card ${sample.id === selectedSampleId ? "is-selected" : ""}`}>
            <div>
              <span>{sample.source}</span>
              <strong>{sample.title}</strong>
              <p>{sample.note}</p>
            </div>
            <div className="sample-actions">
              <button type="button" onClick={() => useSample(sample)}>
                Metni forma al
              </button>
              <a href={sample.url} target="_blank" rel="noreferrer">
                Kaynak <ExternalLink size={13} />
              </a>
            </div>
          </article>
        ))}
      </div>

      <label className="lab-field full-span">
        <span>Rapor metni veya PDF'ten çıkarılan içerik</span>
        <textarea value={caseText} onChange={(event) => setCaseText(event.target.value)} rows={7} />
      </label>

      <div className="upload-row">
        <FileInput label="8D/CAPA dosyası" file={caseFile} setFile={setCaseFile} accept=".pdf,.txt,.md,.csv,.json" />
        <FileInput label="Hata fotoğrafı" file={defectPhoto} setFile={setDefectPhoto} accept="image/*" />
        <FileInput label="Düzeltici kanıt" file={correctivePhoto} setFile={setCorrectivePhoto} accept="image/*" />
        <FileInput label="Ölçüm/etiket" file={measurementPhoto} setFile={setMeasurementPhoto} accept="image/*" />
      </div>

      <div className="meta-grid">
        {[
          ["employee_code", "Task routing kodu"],
          ["role_code", "Rol"],
          ["team_code", "Ekip"],
          ["station_code", "İstasyon"],
        ].map(([key, label]) => (
          <label key={key} className="lab-field">
            <span>{label}</span>
            <input value={meta[key]} onChange={(event) => setMeta((current) => ({ ...current, [key]: event.target.value }))} />
          </label>
        ))}
      </div>
    </section>
  );
}

function FileInput({ label, file, setFile, accept }) {
  return (
    <label className={`file-drop ${file ? "has-file" : ""}`}>
      <input type="file" accept={accept} onChange={(event) => setFile(event.target.files?.[0] || null)} />
      <FileText size={16} aria-hidden="true" />
      <span>{label}</span>
      <strong>{file ? file.name : "Yükle"}</strong>
    </label>
  );
}

function RoiPanel({ roiInputs, setRoiInputs, roiImpact, roiError, roiLoading, estimateRoi }) {
  return (
    <section className="roi-panel" aria-label="Pilot ROI varsayım paneli">
      <div className="roi-copy">
        <span className="node-label">Pilot ROI hypothesis</span>
        <strong>2 saat/hafta varsayımını görünür yapar; garanti tasarruf iddiası üretmez.</strong>
      </div>
      <div className="roi-inputs">
        {[
          ["quality_engineers_in_scope", "Kalite mühendisi"],
          ["review_hours_saved_per_engineer_per_week", "Saat/hafta"],
          ["loaded_hourly_cost_try", "TL/saat"],
          ["incidents_per_month", "Olay/ay"],
          ["repeated_evidence_gap_rate", "Tekrar oranı"],
          ["mentor_closure_hours_before", "Önce kapanış saati"],
          ["mentor_closure_hours_after", "Sonra kapanış saati"],
        ].map(([key, label]) => (
          <label key={key} className="lab-field">
            <span>{label}</span>
            <input
              inputMode="numeric"
              value={roiInputs[key]}
              onChange={(event) => setRoiInputs((current) => ({ ...current, [key]: event.target.value }))}
            />
          </label>
        ))}
      </div>
      <button className="roi-button" type="button" onClick={estimateRoi} disabled={roiLoading}>
        {roiLoading ? <Activity size={15} className="spin-icon" /> : <Calculator size={15} />}
        Pilot varsayımı hesapla
      </button>
      <AnimatePresence>
        {(roiImpact || roiError) && (
          <motion.div
            className={`roi-result ${roiError ? "is-error" : ""}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
          >
            {roiError ? (
              <span>{roiError}</span>
            ) : (
              <>
                <span>{roiImpact.confidence} · gerçek Ford maliyeti değildir</span>
                <strong>{Number(roiImpact.annual_review_time_value || 0).toLocaleString("tr-TR")} TL/yıl review-time varsayımı</strong>
                <small>{roiImpact.formula}</small>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function LiveAnalysisStage({ incident, phase, error, selectedSample }) {
  if (phase === "error") {
    return (
      <div className="live-empty error-state">
        <AlertTriangle size={26} aria-hidden="true" />
        <strong>Canlı analiz durdu</strong>
        <p>{error}</p>
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="live-empty">
        <div className="source-orbit" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <strong>{phase === "loading" ? "Sunucu çalışıyor" : "Rapor bekleniyor"}</strong>
        <p>
          {phase === "loading"
            ? "Belge ajanı rapor alanlarını çıkarıyor. Bu adım gerçek API çağrısıdır."
            : `${selectedSample?.title || "Public report"} kaynağını aç, PDF'i indir veya metni düzenleyip canlı analizi başlat.`}
        </p>
      </div>
    );
  }

  const report = incident.case_report;
  const document = report?.document || {};
  const checklist = report?.checklist || {};
  const readiness = incident.readiness_score || {};

  return (
    <div className="live-result">
      {/* Step 1: Score */}
      <motion.div
        className="live-score-card"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="node-label">Canlı olay</span>
        <strong>{readiness.status === "ready" ? "Readiness düşük risk" : "Readiness aksiyon istiyor"}</strong>
        <div className="score-line">
          <span className="score-value">{readiness.score ?? checklist.score ?? "--"}</span>
          <span>/100</span>
        </div>
        <code>{incident.incident_id}</code>
      </motion.div>

      {/* Step 2: Extracted document fields */}
      <motion.div
        className="live-section"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="live-section-label">
          <FileText size={12} /> Çıkarılan 8D Alanları
          <span className="live-section-badge">{document.source || "heuristic"}</span>
        </span>
        <div className="field-chips">
          {Object.entries(FIELD_LABELS).map(([key, label]) => (
            <span key={key} className={`field-chip ${document[key] ? "chip-found" : "chip-missing"}`}>
              {document[key] ? <CheckCircle2 size={10} /> : <span className="chip-dash">—</span>}
              {label}
            </span>
          ))}
        </div>
      </motion.div>

      {/* Step 3: Skill gaps → Learning tasks loop */}
      {(incident.skill_gaps?.length > 0 || incident.learning_tasks?.length > 0) && (
        <motion.div
          className="live-loop-flow"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="loop-flow-col">
            <span className="node-label">Beceri Açığı</span>
            {(incident.skill_gaps || []).slice(0, 3).map((gap, i) => (
              <div key={i} className="gap-row">
                <span className="gap-skill-tag">{displaySkillId(gap.skill_id)}</span>
                <span className="gap-title">{gap.title}</span>
              </div>
            ))}
            {!incident.skill_gaps?.length && (
              <span className="gap-none">Kritik açık yok</span>
            )}
          </div>
          <div className="loop-flow-arrow" aria-hidden="true">→</div>
          <div className="loop-flow-col">
            <span className="node-label">Öğrenme Görevi</span>
            {(incident.learning_tasks || []).slice(0, 2).map((task, i) => (
              <div key={i} className="task-row">
                <CheckCircle2 size={11} className="task-icon" />
                <span>{task.title}</span>
              </div>
            ))}
            {!incident.learning_tasks?.length && (
              <span className="gap-none">Görev gerekmedi</span>
            )}
            <div className="task-mentor-hint">
              <ShieldCheck size={11} />
              <span>Mentor onayı bekleniyor →</span>
            </div>
          </div>
        </motion.div>
      )}

      {/* Step 4: Checklist issues */}
      {checklist.issues?.length > 0 && (
        <div className="issue-list">
          {checklist.issues.slice(0, 4).map((issue) => (
            <article key={issue.code}>
              <span>{issue.severity}</span>
              <strong>{issue.title}</strong>
              <p>{issue.suggested_action}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveProofStrip({ incident }) {
  if (!incident) {
    return (
      <div className="proof-pipeline-row">
        <div className="proof-pipe-step">
          <FileText size={13} className="pipe-icon" />
          <span className="pipe-label">Rapor</span>
          <span className="pipe-sub">8D · CAPA · PDF</span>
        </div>
        <span className="pipe-arrow" aria-hidden="true">→</span>
        <div className="proof-pipe-step pipe-ai">
          <Activity size={13} className="pipe-icon" />
          <span className="pipe-label">Belge Ajanı</span>
          <span className="pipe-sub">D2–D8 alanları çıkarır</span>
        </div>
        <span className="pipe-arrow" aria-hidden="true">→</span>
        <div className="proof-pipe-step pipe-rule">
          <Calculator size={13} className="pipe-icon" />
          <span className="pipe-label">Kural Motoru</span>
          <span className="pipe-sub">7 beceri · 100-ceza formülü</span>
        </div>
        <span className="pipe-arrow" aria-hidden="true">→</span>
        <div className="proof-pipe-step pipe-out">
          <ShieldCheck size={13} className="pipe-icon" />
          <span className="pipe-label">Mentor Kapısı</span>
          <span className="pipe-sub">Readiness skoru + görev</span>
        </div>
      </div>
    );
  }

  const report = incident.case_report || {};
  const checklist = report.checklist || {};
  const firstGap = incident.skill_gaps?.[0];
  const readiness = incident.readiness_score || {};
  return (
    <div className="proof-strip">
      <ProofChip label="Case score" value={`${checklist.score ?? "--"}/100`} strong />
      <ProofChip label="Issue" value={`${checklist.issues?.length || 0} checklist açığı`} />
      <ProofChip label="Readiness riski" value={firstGap?.title || "Yok"} tone={firstGap ? "risk" : "verified"} />
      <ProofChip label="Operational readiness" value={readiness.explanation || `${readiness.score ?? "--"}/100`} strong />
      <ProofChip label="Denetim izi" value={`${incident.audit_events?.length || 0} kayıt`} />
    </div>
  );
}

function LiveActionSheet({ incident, visible }) {
  const task = incident?.learning_tasks?.[0];
  return (
    <AnimatePresence>
      {visible && (
        <motion.aside
          className="action-sheet live-action"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="action-icon" aria-hidden="true">
            <CheckCircle2 size={20} />
          </div>
          <div>
            <span className="node-label">Sunucu çıktısı</span>
            <strong>{task?.title || "Mentor onayı gerekmedi"}</strong>
            <p>{task ? "Mentor görevi açıldı; onay gelmeden readiness kapanmış sayılmaz." : "Kontrol listesi temiz görünüyor."}</p>
          </div>
          <ArrowRight size={18} aria-hidden="true" />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function EvidenceField({ active, reducedMotion }) {
  return (
    <div className={`evidence-field ${active ? "is-active" : ""} ${reducedMotion ? "is-reduced" : ""}`} aria-hidden="true">
      <div className="field-plane field-plane-one" />
      <div className="field-plane field-plane-two" />
      <div className="field-scanline" />
    </div>
  );
}

const GATE_STATUS_CFG = {
  CLEARED: { label: "CLEARED", tone: "verified" },
  NEEDS_MENTOR_REVIEW: { label: "MENTOR ONAYI BEKLENİYOR", tone: "warning" },
  ACTION_REQUIRED: { label: "AKSİYON GEREKLİ", tone: "risk" },
  UNKNOWN: { label: "MANUEL İNCELEME", tone: "neutral" },
};

const DEMO_GATE_FALLBACK = {
  gate_status: "ACTION_REQUIRED",
  readiness_score: 32,
  risk_level: "critical",
  station_code: "station-final-inspection",
  shift_code: "A",
  skill_id: "effectiveness_verification",
  title: "Etkinlik doğrulama",
  reason: "3 olayda tekrar eden etkinlik doğrulama kanıt eksikliği tespit edildi.",
  micro_practice: {
    prompt: "Düzeltici aksiyonun işe yaradığını kanıtlayan tarihli ölçüm veya kaydı göster.",
    expected_evidence: ["Tarih", "Ölçülebilir sonuç", "Mentor onayı"],
  },
  mentor_required: true,
  claims_boundary: "Bu gate fiziksel erişim kontrolü değildir. Kişi skorlamaz. Mentor onaylı koçluk ve vardiya readiness görünürlüğü için demo durumudur.",
};

function GateSimulationPanel({
  gateData,
  gateStatus,
  mentorApproving,
  visible,
  onAcknowledge,
  onMentorApprove,
}) {
  const data = gateData || DEMO_GATE_FALLBACK;
  const cfg = GATE_STATUS_CFG[gateStatus] || GATE_STATUS_CFG.ACTION_REQUIRED;
  const isCleared = gateStatus === "CLEARED";
  const needsMentor = gateStatus === "NEEDS_MENTOR_REVIEW";
  const actionRequired = gateStatus === "ACTION_REQUIRED";

  return (
    <AnimatePresence>
      {visible && (
        <motion.section
          className="gate-panel"
          aria-label="Vardiya başlangıç kapısı simülasyonu"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="gate-panel-header">
            <div className="gate-panel-title">
              <ShieldCheck size={15} aria-hidden="true" />
              <span>Vardiya Başlangıç Kapısı</span>
              <span className="gate-sim-badge">Simülasyon</span>
            </div>
            <span className={`gate-status-chip tone-${cfg.tone}`}>{cfg.label}</span>
          </div>

          <div className="gate-panel-meta">
            <span>İstasyon: <strong>{data.station_code}</strong></span>
            <span>Vardiya: <strong>{data.shift_code}</strong></span>
            <span>Puan: <strong>{data.readiness_score}/100</strong></span>
          </div>

          <AnimatePresence mode="wait">
            {isCleared ? (
              <motion.div
                key="cleared"
                className="gate-cleared"
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              >
                <CheckCircle2 size={18} aria-hidden="true" />
                <div>
                  <strong>Mentor onayı alındı</strong>
                  <p>Vardiya readiness riski kapatıldı. İstasyon hazır.</p>
                </div>
              </motion.div>
            ) : (
              <motion.div key="risk" className="gate-risk-block" initial={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="gate-risk-skill">
                  <span className="node-label">Açık beceri riski</span>
                  <strong>{data.title || "Etkinlik doğrulama"}</strong>
                </div>
                <div className="gate-practice">
                  <span className="node-label">Mikro pratik</span>
                  <p>{data.micro_practice?.prompt}</p>
                  {data.micro_practice?.expected_evidence?.length > 0 && (
                    <ul className="gate-evidence-list">
                      {data.micro_practice.expected_evidence.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  )}
                </div>
                {needsMentor && (
                  <motion.p
                    className="gate-ack-note"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    Operatör mikro pratiği okudu. Mentor onayı bekleniyor — readiness yalnızca mentor onayıyla kapanır.
                  </motion.p>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {!isCleared && (
            <div className="gate-panel-actions">
              {actionRequired && (
                <button className="gate-btn gate-btn-secondary" type="button" onClick={onAcknowledge}>
                  Okudum, kabul ettim
                </button>
              )}
              <button
                className="gate-btn gate-btn-primary"
                type="button"
                onClick={onMentorApprove}
                disabled={mentorApproving}
              >
                {mentorApproving ? "Onaylanıyor…" : "Mentor Onayla"}
              </button>
            </div>
          )}

          <p className="gate-claims-boundary">{data.claims_boundary}</p>
        </motion.section>
      )}
    </AnimatePresence>
  );
}

function Button({ children, ...props }) {
  return (
    <button className="primary-button" type="button" {...props}>
      {children}
    </button>
  );
}

function StatusPill({ label, tone = "neutral" }) {
  return <span className={`status-pill tone-${tone}`}>{label}</span>;
}

function ProofChip({ label, value, tone = "neutral", strong = false }) {
  return (
    <article className={`proof-chip tone-${tone} ${strong ? "is-strong" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function apiHeaders() {
  return API_KEY ? { "X-KANIT-API-Key": API_KEY } : {};
}

function displaySkillId(skillId) {
  const labels = {
    effectiveness_verification: "etkinlik_dogrulama",
    visual_evidence_capture: "gorsel_kanit_yakalama",
    root_cause_analysis: "kok_neden_analizi",
  };
  return labels[skillId] || skillId;
}

/* ── NEW UTILITY COMPONENTS ───────────────────────────── */

function AnimatedCounter({ to, suffix = "", duration = 1.5 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const t0 = Date.now();
    const tick = () => {
      const p = Math.min((Date.now() - t0) / (duration * 1000), 1);
      setVal(Math.round((1 - Math.pow(1 - p, 3)) * to));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView, to, duration]);

  return (
    <span ref={ref} style={{ fontVariantNumeric: "tabular-nums" }}>
      {val}{suffix}
    </span>
  );
}

function PipelineConnector({ active, delay = 0 }) {
  return (
    <div className="pipeline-connector" aria-hidden="true">
      <motion.div
        className="pipeline-connector-fill"
        initial={{ scaleX: 0 }}
        animate={active ? { scaleX: 1 } : { scaleX: 0 }}
        transition={{ duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] }}
      />
    </div>
  );
}

export default App;
