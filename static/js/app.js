/**
 * Presidency University - Decentralized Academic Credential & Skill Verification System
 * Client-Side Application Controller
 */

// Global Application State
let state = {
  currentUser: null,
  token: localStorage.getItem("pu_session_token") || null,
  currentVerifiedData: null,
  degreeCatalog: [],
  studentsList: []
};

// -----------------------------------------------------------------------------
// 1. Initialization
// -----------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  await fetchDegreeCatalog();
  await checkActiveSession();
  
  // Default to verification view
  switchTab("verify");

  // Load university identity for identity view
  loadUniversityIdentity();
  loadLedgerBlocks();
});

// Toast notification helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  const bgColors = {
    success: "bg-emerald-600 text-white",
    error: "bg-rose-600 text-white",
    info: "bg-punavy-800 text-white border border-amber-400/40",
    warning: "bg-amber-600 text-white"
  };

  const icons = {
    success: '<i class="fa-solid fa-circle-check"></i>',
    error: '<i class="fa-solid fa-circle-exclamation"></i>',
    info: '<i class="fa-solid fa-circle-info"></i>',
    warning: '<i class="fa-solid fa-triangle-exclamation"></i>'
  };

  toast.className = `px-4 py-3 rounded-lg shadow-xl text-xs font-semibold flex items-center gap-2.5 transition-all transform duration-300 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `${icons[type] || icons.info} <span>${message}</span>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Clipboard copy helper
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText || el.textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied to clipboard!", "success");
  });
}

// -----------------------------------------------------------------------------
// 2. Navigation & View Routing
// -----------------------------------------------------------------------------

function switchTab(tabId) {
  const views = ["verify", "student", "teacher", "admin", "ledger", "identity"];
  views.forEach(v => {
    const el = document.getElementById(`view-${v}`);
    const navBtn = document.getElementById(`nav-tab-${v}`);
    if (el) el.classList.add("hidden");
    if (navBtn) {
      navBtn.classList.remove("text-amber-300", "bg-white/10");
      navBtn.classList.add("text-slate-200");
    }
  });

  const activeView = document.getElementById(`view-${tabId}`);
  const activeNav = document.getElementById(`nav-tab-${tabId}`);

  if (activeView) activeView.classList.remove("hidden");
  if (activeNav) {
    activeNav.classList.remove("text-slate-200");
    activeNav.classList.add("text-amber-300", "bg-white/10");
  }

  // Trigger data refresh on tab switch
  if (tabId === "student" && state.currentUser) loadStudentDashboard();
  if (tabId === "teacher" && state.currentUser) loadTeacherDashboard();
  if (tabId === "admin" && state.currentUser) loadAdminDashboard();
  if (tabId === "ledger") loadLedgerBlocks();
  if (tabId === "identity") loadUniversityIdentity();
}

// -----------------------------------------------------------------------------
// 3. Authentication & Session Management
// -----------------------------------------------------------------------------

async function checkActiveSession() {
  if (!state.token) {
    updateAuthHeaderUI(null);
    return;
  }

  try {
    const res = await fetch("/api/auth/me", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      state.currentUser = data.user;
      updateAuthHeaderUI(data.user);
    } else {
      localStorage.removeItem("pu_session_token");
      state.token = null;
      state.currentUser = null;
      updateAuthHeaderUI(null);
    }
  } catch (err) {
    console.error("Session check error:", err);
  }
}

function updateAuthHeaderUI(user) {
  const guestBtns = document.getElementById("guest-buttons");
  const userWidget = document.getElementById("user-profile-widget");
  const studentTab = document.getElementById("nav-tab-student");
  const teacherTab = document.getElementById("nav-tab-teacher");
  const adminTab = document.getElementById("nav-tab-admin");

  // Reset tab visibility
  if (studentTab) studentTab.classList.add("hidden");
  if (teacherTab) teacherTab.classList.add("hidden");
  if (adminTab) adminTab.classList.add("hidden");

  if (user) {
    if (guestBtns) guestBtns.classList.add("hidden");
    if (userWidget) userWidget.classList.remove("hidden"), userWidget.classList.add("flex");
    
    document.getElementById("header-user-name").innerText = user.full_name;
    document.getElementById("header-user-role-badge").innerText = `${user.role.toUpperCase()} • ${user.identifier}`;

    // Show appropriate role tab
    if (user.role === "student" && studentTab) studentTab.classList.remove("hidden"), studentTab.classList.add("flex");
    if (user.role === "teacher" && teacherTab) teacherTab.classList.remove("hidden"), teacherTab.classList.add("flex");
    if (user.role === "admin" && adminTab) adminTab.classList.remove("hidden"), adminTab.classList.add("flex");
  } else {
    if (guestBtns) guestBtns.classList.remove("hidden");
    if (userWidget) userWidget.classList.add("hidden"), userWidget.classList.remove("flex");
  }
}

function openAuthModal(tab = "login") {
  const modal = document.getElementById("auth-modal");
  if (modal) modal.classList.remove("hidden");
  toggleAuthTab(tab);
}

function closeAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) modal.classList.add("hidden");
}

function toggleAuthTab(tab) {
  const loginForm = document.getElementById("login-form");
  const regForm = document.getElementById("register-form");
  const tabLogin = document.getElementById("auth-tab-btn-login");
  const tabReg = document.getElementById("auth-tab-btn-register");

  if (tab === "login") {
    loginForm.classList.remove("hidden");
    regForm.classList.add("hidden");
    tabLogin.classList.add("border-punavy-800", "text-punavy-800");
    tabLogin.classList.remove("border-transparent", "text-slate-500");
    tabReg.classList.remove("border-punavy-800", "text-punavy-800");
    tabReg.classList.add("border-transparent", "text-slate-500");
  } else {
    loginForm.classList.add("hidden");
    regForm.classList.remove("hidden");
    tabReg.classList.add("border-punavy-800", "text-punavy-800");
    tabReg.classList.remove("border-transparent", "text-slate-500");
    tabLogin.classList.remove("border-punavy-800", "text-punavy-800");
    tabLogin.classList.add("border-transparent", "text-slate-500");
  }
}

function selectRegisterRole(role) {
  document.getElementById("reg-role").value = role;
  const roles = ["student", "teacher", "admin"];
  roles.forEach(r => {
    const pill = document.getElementById(`role-pill-${r}`);
    if (r === role) {
      pill.className = "py-2 px-1 text-center rounded-lg border-2 border-amber-500 bg-amber-50 text-amber-900 font-bold text-xs";
    } else {
      pill.className = "py-2 px-1 text-center rounded-lg border border-slate-200 hover:border-slate-300 text-slate-700 font-semibold text-xs";
    }
  });

  const label = document.getElementById("reg-identifier-label");
  const input = document.getElementById("reg-identifier");
  if (role === "student") {
    label.innerText = "University Seat Number (USN)";
    input.placeholder = "e.g. 20241CSE0999";
  } else if (role === "teacher") {
    label.innerText = "Faculty Identification Number (FID)";
    input.placeholder = "e.g. PU-FAC-405";
  } else {
    label.innerText = "University Employee Code (EID)";
    input.placeholder = "e.g. PU-REG-008";
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Login failed.", "error");
      return;
    }

    state.token = data.token;
    state.currentUser = data.user;
    localStorage.setItem("pu_session_token", data.token);

    updateAuthHeaderUI(data.user);
    closeAuthModal();
    showToast(`Welcome back, ${data.user.full_name}!`, "success");

    // Automatically navigate to role view
    switchTab(data.user.role);
  } catch (err) {
    showToast("Network error during login.", "error");
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const payload = {
    username: document.getElementById("reg-username").value.trim(),
    email: document.getElementById("reg-email").value.trim(),
    password: document.getElementById("reg-password").value,
    role: document.getElementById("reg-role").value,
    full_name: document.getElementById("reg-fullname").value.trim(),
    identifier: document.getElementById("reg-identifier").value.trim(),
    department: document.getElementById("reg-department").value
  };

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Registration failed.", "error");
      return;
    }

    state.token = data.token;
    state.currentUser = data.user;
    localStorage.setItem("pu_session_token", data.token);

    updateAuthHeaderUI(data.user);
    closeAuthModal();
    showToast(`Account created! Generated DID: ${data.user.did.substring(0, 22)}...`, "success");

    switchTab(data.user.role);
  } catch (err) {
    showToast("Network error during registration.", "error");
  }
}

async function logoutUser() {
  if (state.token) {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.token}` }
    });
  }
  localStorage.removeItem("pu_session_token");
  state.token = null;
  state.currentUser = null;
  updateAuthHeaderUI(null);
  showToast("Logged out of Presidency University session.", "info");
  switchTab("verify");
}

// Quick evaluator login switch
async function quickLogin(role) {
  const credentials = {
    admin: { username: "admin", password: "admin123" },
    teacher: { username: "prof_sharma", password: "teacher123" },
    student: { username: "arjun_reddy", password: "student123" }
  };

  const cred = credentials[role];
  if (!cred) return;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cred)
    });
    const data = await res.json();
    if (res.ok) {
      state.token = data.token;
      state.currentUser = data.user;
      localStorage.setItem("pu_session_token", data.token);
      updateAuthHeaderUI(data.user);
      showToast(`Switched to Demo ${role.toUpperCase()} (${data.user.full_name})`, "success");
      switchTab(role);
    }
  } catch (e) {
    console.error(e);
  }
}

// -----------------------------------------------------------------------------
// 4. Degree Catalog Loader
// -----------------------------------------------------------------------------

async function fetchDegreeCatalog() {
  try {
    const res = await fetch("/api/catalog/degrees");
    if (res.ok) {
      const data = await res.json();
      state.degreeCatalog = data.catalog || [];
    }
  } catch (err) {
    console.error("Failed to fetch degree catalog:", err);
  }
}

// -----------------------------------------------------------------------------
// 5. Public Zero-Trust Verification Engine
// -----------------------------------------------------------------------------

async function verifyById() {
  const input = document.getElementById("verify-search-input").value.trim();
  if (!input) {
    showToast("Please enter a Credential ID or Student USN.", "warning");
    return;
  }
  executeVerification({ credential_id: input });
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const json = JSON.parse(e.target.result);
      executeVerification(json);
    } catch (err) {
      showToast("Invalid JSON file uploaded.", "error");
    }
  };
  reader.readAsText(file);
}

function demoVerifySample() {
  document.getElementById("verify-search-input").value = "PU-2025-BTECH-00452";
  verifyById();
}

async function demoTamperTest() {
  showToast("Simulating tampered credential (CGPA forged from 9.24 to 9.99)...", "warning");

  // Load authentic sample then tamper with it
  try {
    const res = await fetch("/api/student/credential/PU-2025-BTECH-00452/export");
    if (res.ok) {
      const vc = await res.json();
      // Tamper with CGPA
      vc.credentialSubject.cgpa = "9.99";
      // Notice: leaf_hash remains the original, creating a hash mismatch!
      executeVerification(vc);
    }
  } catch (err) {
    console.error("Tamper test error:", err);
  }
}

async function executeVerification(payload) {
  showToast("Running 4-Tier Cryptographic Audit...", "info");

  try {
    const res = await fetch("/api/verify/credential", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Verification failed.", "error");
      return;
    }

    state.currentVerifiedData = data;
    renderVerificationResults(data);

    if (data.overall_verified) {
      confetti({ particleCount: 70, spread: 60, origin: { y: 0.6 } });
    }
  } catch (err) {
    showToast("Verification request failed.", "error");
  }
}

function renderVerificationResults(data) {
  const container = document.getElementById("verification-results-container");
  container.classList.remove("hidden");

  const banner = document.getElementById("verification-banner");
  const iconBox = document.getElementById("verification-icon-box");
  const title = document.getElementById("verification-verdict-title");
  const subtitle = document.getElementById("verification-verdict-subtitle");
  const timePill = document.getElementById("verification-time-pill");
  const viewCertBtn = document.getElementById("view-certificate-btn");

  timePill.innerText = `${data.verification_metrics.verification_time_ms} ms (Verified)`;

  if (data.overall_verified) {
    banner.className = "rounded-xl p-5 border border-emerald-300 bg-emerald-50/70 text-emerald-950 flex flex-wrap items-center justify-between gap-4";
    iconBox.className = "w-12 h-12 rounded-full bg-emerald-500 text-white flex items-center justify-center text-2xl shadow-sm";
    iconBox.innerHTML = '<i class="fa-solid fa-check"></i>';
    title.innerText = "100% Cryptographically Authenticated";
    subtitle.innerText = "Officially issued by Presidency University. Mathematical integrity, Merkle inclusion, and university signature confirmed.";
    viewCertBtn.classList.remove("hidden");
  } else {
    banner.className = "rounded-xl p-5 border border-rose-300 bg-rose-50/70 text-rose-950 flex flex-wrap items-center justify-between gap-4";
    iconBox.className = "w-12 h-12 rounded-full bg-rose-500 text-white flex items-center justify-center text-2xl shadow-sm";
    iconBox.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    title.innerText = "Verification Failed - Tampering or Revocation Detected";
    subtitle.innerText = data.reasons && data.reasons.length ? data.reasons.join(" | ") : "Cryptographic proofs did not match Presidency University records.";
    viewCertBtn.classList.add("hidden");
  }

  // Render 4-step pipeline cards
  const stepsGrid = document.getElementById("pipeline-steps-grid");
  stepsGrid.innerHTML = "";

  data.verification_metrics.steps.forEach(st => {
    const card = document.createElement("div");
    const isPass = st.passed;
    card.className = `step-card pu-card p-4 space-y-2 border-2 ${isPass ? 'passed' : 'failed'}`;
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500">Step ${st.step}</span>
        <span class="text-xs font-bold px-2 py-0.5 rounded-full ${isPass ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
          ${isPass ? '<i class="fa-solid fa-check mr-1"></i> PASSED' : '<i class="fa-solid fa-xmark mr-1"></i> FAILED'}
        </span>
      </div>
      <h5 class="text-xs font-bold text-slate-800">${st.title}</h5>
      <p class="text-[11px] text-slate-600 leading-tight">${st.description}</p>
    `;
    stepsGrid.appendChild(card);
  });

  // Populate candidate details
  const cred = data.credential_details || {};
  document.getElementById("res-student-name").innerText = cred.student_name || "N/A";
  document.getElementById("res-student-usn").innerText = cred.student_usn || "N/A";
  document.getElementById("res-degree-type").innerText = cred.degree_type || "N/A";
  document.getElementById("res-major-spec").innerText = cred.major_specialization || "N/A";
  document.getElementById("res-cgpa").innerText = `${cred.cgpa || '0.00'} / 10.00`;
  document.getElementById("res-honors").innerText = cred.honors || "N/A";
  document.getElementById("res-year").innerText = cred.completion_year || "N/A";

  // Skills tags
  const skillsContainer = document.getElementById("res-skills-tags");
  skillsContainer.innerHTML = "";
  (cred.skills || []).forEach(sk => {
    const tag = document.createElement("span");
    tag.className = "px-2.5 py-1 rounded-md bg-amber-50 text-amber-900 border border-amber-200 text-[11px] font-semibold";
    tag.innerHTML = `<i class="fa-solid fa-badge-check text-amber-600 mr-1"></i> ${sk}`;
    skillsContainer.appendChild(tag);
  });

  // Cryptographic evidence
  const proofs = data.cryptographic_proofs || {};
  document.getElementById("res-leaf-hash").innerText = proofs.leaf_hash || "N/A";
  document.getElementById("res-merkle-root").innerText = proofs.merkle_root || "N/A";
  document.getElementById("res-root-signature").innerText = proofs.root_signature || "N/A";
  document.getElementById("res-univ-did").innerText = proofs.university_did || "N/A";
  document.getElementById("res-block-num").innerText = cred.block_number || "Pending";
  document.getElementById("res-batch-id").innerText = cred.batch_id || "Unbatched";

  // Smooth scroll into results
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// -----------------------------------------------------------------------------
// 6. Official Digital Degree Certificate View
// -----------------------------------------------------------------------------

function openOfficialCertificateModal() {
  if (!state.currentVerifiedData || !state.currentVerifiedData.credential_details) return;
  const cred = state.currentVerifiedData.credential_details;

  document.getElementById("cert-student-name").innerText = cred.student_name;
  document.getElementById("cert-student-usn").innerText = cred.student_usn;
  document.getElementById("cert-degree-type").innerText = cred.degree_type;
  document.getElementById("cert-major-spec").innerText = cred.major_specialization;
  document.getElementById("cert-honors").innerText = cred.honors ? `(${cred.honors})` : "";
  document.getElementById("cert-cred-id").innerText = cred.credential_id;
  document.getElementById("cert-block-num").innerText = cred.block_number || "101";
  document.getElementById("cert-issued-date").innerText = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  // Generate QR code
  const qrcodeBox = document.getElementById("diploma-qrcode-box");
  qrcodeBox.innerHTML = "";
  const verifyUrl = `${window.location.origin}/?verify=${encodeURIComponent(cred.credential_id)}`;
  new QRCode(qrcodeBox, {
    text: verifyUrl,
    width: 64,
    height: 64,
    colorDark: "#0B2240",
    colorLight: "#FFFFFF",
    correctLevel: QRCode.CorrectLevel.M
  });

  document.getElementById("certificate-modal").classList.remove("hidden");
}

function closeOfficialCertificateModal() {
  document.getElementById("certificate-modal").classList.add("hidden");
}

async function downloadVerifiedJSON() {
  if (!state.currentVerifiedData || !state.currentVerifiedData.credential_details) return;
  const credId = state.currentVerifiedData.credential_details.credential_id;

  try {
    const res = await fetch(`/api/student/credential/${encodeURIComponent(credId)}/export`);
    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${credId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast(`Exported Verifiable Credential: ${credId}.json`, "success");
    }
  } catch (err) {
    showToast("Failed to export JSON.", "error");
  }
}

// -----------------------------------------------------------------------------
// 7. Student Locker & Digital Wallet
// -----------------------------------------------------------------------------

async function loadStudentDashboard() {
  if (!state.currentUser) return;
  document.getElementById("student-portal-name").innerText = state.currentUser.full_name;
  document.getElementById("student-portal-usn").innerText = state.currentUser.identifier;
  document.getElementById("student-portal-dept").innerText = state.currentUser.department;
  document.getElementById("student-portal-did").innerText = state.currentUser.did;

  try {
    const res = await fetch("/api/student/credentials", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      renderStudentCredentials(data.credentials || []);
    }
  } catch (err) {
    console.error("Student credentials error:", err);
  }
}

function renderStudentCredentials(creds) {
  const grid = document.getElementById("student-credentials-grid");
  grid.innerHTML = "";

  if (creds.length === 0) {
    grid.innerHTML = `
      <div class="col-span-2 pu-card p-8 text-center text-slate-500">
        <i class="fa-solid fa-folder-open text-4xl text-slate-300 mb-2"></i>
        <h4 class="font-bold text-slate-700">No Credentials Issued Yet</h4>
        <p class="text-xs">Your academic department faculty has not yet endorsed your degree or skill records.</p>
      </div>
    `;
    return;
  }

  creds.forEach(c => {
    const card = document.createElement("div");
    const isSealed = c.status === "university_sealed";
    const isRevoked = c.status === "revoked";

    card.className = "pu-card p-5 space-y-4 border-t-4 " + (isRevoked ? "border-red-600" : (isSealed ? "border-amber-500" : "border-blue-500"));

    card.innerHTML = `
      <div class="flex justify-between items-start gap-2">
        <div>
          <span class="text-[10px] font-mono text-slate-400 block">${c.credential_id}</span>
          <h4 class="text-base font-bold text-punavy-800">${c.degree_type} in ${c.major_specialization}</h4>
          <p class="text-xs text-slate-600">${c.honors || 'Degree Completion'}</p>
        </div>
        <span class="text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider ${
          isRevoked ? 'bg-red-100 text-red-800' : (isSealed ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800')
        }">
          ${isRevoked ? 'REVOKED' : (isSealed ? '<i class="fa-solid fa-stamp mr-1"></i> SEALED' : 'FACULTY ENDORSED')}
        </span>
      </div>

      <div class="grid grid-cols-3 gap-2 text-xs bg-slate-50 p-2.5 rounded-lg border border-slate-100">
        <div>
          <span class="text-slate-400 block text-[10px]">CGPA</span>
          <strong class="text-amber-700 font-bold">${c.cgpa.toFixed(2)}</strong>
        </div>
        <div>
          <span class="text-slate-400 block text-[10px]">Credits</span>
          <strong class="text-slate-800">${c.credits_earned}</strong>
        </div>
        <div>
          <span class="text-slate-400 block text-[10px]">Ledger Block</span>
          <strong class="text-slate-800 font-mono">${c.block_number ? '#' + c.block_number : 'Pending'}</strong>
        </div>
      </div>

      <div>
        <span class="text-[10px] font-semibold text-slate-400 block mb-1">Endorsed Skills:</span>
        <div class="flex flex-wrap gap-1">
          ${(c.skills || []).map(sk => `<span class="bg-amber-100/70 text-amber-900 text-[10px] px-2 py-0.5 rounded font-medium">${sk}</span>`).join('')}
        </div>
      </div>

      <div class="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
        <button onclick="viewStudentCert('${c.credential_id}')" class="flex-1 navy-btn py-1.5 px-3 rounded text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm">
          <i class="fa-solid fa-certificate text-amber-400"></i> View Degree
        </button>
        <button onclick="inspectMerkleProof('${c.credential_id}', '${c.leaf_hash}', '${encodeURIComponent(JSON.stringify(c.merkle_proof))}')" class="px-3 py-1.5 rounded text-xs font-semibold border border-slate-300 hover:bg-slate-50 text-slate-700" title="Inspect Merkle Proof">
          <i class="fa-solid fa-network-wired"></i> Proof
        </button>
        <button onclick="downloadCredentialById('${c.credential_id}')" class="px-3 py-1.5 rounded text-xs font-semibold border border-slate-300 hover:bg-slate-50 text-slate-700" title="Download Verifiable Credential">
          <i class="fa-solid fa-download"></i>
        </button>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function viewStudentCert(credId) {
  // Run verification to load into verified state, then open cert
  await executeVerification({ credential_id: credId });
  openOfficialCertificateModal();
}

function downloadCredentialById(credId) {
  window.open(`/api/student/credential/${encodeURIComponent(credId)}/export`, "_blank");
}

function inspectMerkleProof(credId, leafHash, encodedProof) {
  const proof = JSON.parse(decodeURIComponent(encodedProof));
  document.getElementById("modal-merkle-leaf").innerText = leafHash;
  document.getElementById("modal-merkle-root").innerText = state.currentVerifiedData?.cryptographic_proofs?.merkle_root || "Refer to University Block Header";

  const container = document.getElementById("modal-merkle-steps");
  container.innerHTML = "";

  if (!proof || proof.length === 0) {
    container.innerHTML = `<div class="text-xs text-slate-400 p-2">Single leaf batch or pending inclusion root.</div>`;
  } else {
    proof.forEach((step, idx) => {
      const div = document.createElement("div");
      div.className = "p-2 bg-slate-50 border border-slate-200 rounded text-xs flex justify-between items-center font-mono";
      div.innerHTML = `
        <span class="text-slate-500 font-sans">Hop ${idx + 1} (${step.position}):</span>
        <span class="text-punavy-800 break-all">${step.hash.substring(0, 20)}...</span>
      `;
      container.appendChild(div);
    });
  }

  document.getElementById("merkle-modal").classList.remove("hidden");
}

function closeMerkleModal() {
  document.getElementById("merkle-modal").classList.add("hidden");
}

// -----------------------------------------------------------------------------
// 8. Faculty / Teacher Portal
// -----------------------------------------------------------------------------

async function loadTeacherDashboard() {
  if (!state.currentUser) return;
  document.getElementById("teacher-portal-name").innerText = state.currentUser.full_name;
  document.getElementById("teacher-portal-id").innerText = state.currentUser.identifier;
  document.getElementById("teacher-portal-dept").innerText = `${state.currentUser.department} • ${state.currentUser.sub_role || 'Faculty'}`;

  try {
    const res = await fetch("/api/teacher/credentials/my-submissions", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      renderTeacherSubmissions(data.submissions || []);
    }
  } catch (err) {
    console.error("Submissions load error:", err);
  }
}

function renderTeacherSubmissions(items) {
  const tbody = document.getElementById("teacher-submissions-tbody");
  tbody.innerHTML = "";

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-400">No credentials endorsed yet. Click 'Endorse New Academic Credential' to create one.</td></tr>`;
    return;
  }

  items.forEach(it => {
    const tr = document.createElement("tr");
    const isSealed = it.status === "university_sealed";
    tr.innerHTML = `
      <td class="py-2.5 px-3 font-semibold text-slate-800">${it.student_name}</td>
      <td class="py-2.5 px-3 font-mono">${it.student_usn}</td>
      <td class="py-2.5 px-3 font-semibold text-punavy-800">${it.degree_type}</td>
      <td class="py-2.5 px-3">${it.major_specialization}</td>
      <td class="py-2.5 px-3 font-bold text-amber-700">${it.cgpa.toFixed(2)}</td>
      <td class="py-2.5 px-3">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${
          isSealed ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
        }">
          ${isSealed ? 'SEALED & ISSUED' : 'PENDING REGISTRAR'}
        </span>
      </td>
      <td class="py-2.5 px-3 font-mono">${it.block_number ? '#' + it.block_number : 'Unbatched'}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function openEndorseModal() {
  // Fetch available students
  try {
    const res = await fetch("/api/teacher/students", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      state.studentsList = data.students || [];
      const select = document.getElementById("endorse-student-select");
      select.innerHTML = state.studentsList.map(s => `
        <option value="${s.id}">${s.full_name} (${s.usn}) - ${s.department}</option>
      `).join('');
    }
  } catch (err) {
    console.error("Failed to load students:", err);
  }

  // Populate degrees dropdown
  const degSelect = document.getElementById("endorse-degree-program");
  degSelect.innerHTML = state.degreeCatalog.map(d => `
    <option value="${d.code}">${d.degree_type} - ${d.name}</option>
  `).join('');

  onDegreeProgramChange();
  document.getElementById("endorse-modal").classList.remove("hidden");
}

function closeEndorseModal() {
  document.getElementById("endorse-modal").classList.add("hidden");
}

function onDegreeProgramChange() {
  const code = document.getElementById("endorse-degree-program").value;
  const item = state.degreeCatalog.find(d => d.code === code);
  if (!item) return;

  const specSelect = document.getElementById("endorse-specialization");
  specSelect.innerHTML = item.specializations.map(s => `<option value="${s}">${s}</option>`).join('');

  // Pre-fill default skills
  document.getElementById("endorse-skills").value = (item.default_skills || []).join(", ");
}

async function handleEndorseSubmit(e) {
  e.preventDefault();
  const studentId = parseInt(document.getElementById("endorse-student-select").value);
  const code = document.getElementById("endorse-degree-program").value;
  const item = state.degreeCatalog.find(d => d.code === code);
  const spec = document.getElementById("endorse-specialization").value;
  const cgpa = parseFloat(document.getElementById("endorse-cgpa").value);
  const year = parseInt(document.getElementById("endorse-year").value);
  const credits = parseInt(document.getElementById("endorse-credits").value);
  const honors = document.getElementById("endorse-honors").value.trim();
  const rawSkills = document.getElementById("endorse-skills").value;
  const skills = rawSkills.split(",").map(s => s.trim()).filter(s => s.length > 0);

  const payload = {
    student_id: studentId,
    degree_type: item ? item.degree_type : "B.Tech",
    major_specialization: spec,
    cgpa: cgpa,
    completion_year: year,
    credits_earned: credits,
    honors: honors,
    skills: skills
  };

  try {
    const res = await fetch("/api/teacher/credentials/endorse", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Endorsement failed.", "error");
      return;
    }

    showToast("Credential digitally endorsed! Submitted to Registrar for Merkle batching.", "success");
    closeEndorseModal();
    loadTeacherDashboard();
  } catch (err) {
    showToast("Endorsement network error.", "error");
  }
}

// -----------------------------------------------------------------------------
// 9. Admin / Registrar Console & Merkle Batch Sealing
// -----------------------------------------------------------------------------

async function loadAdminDashboard() {
  if (!state.currentUser) return;

  // 1. Fetch stats
  try {
    const res = await fetch("/api/admin/stats", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      document.getElementById("admin-stat-issued").innerText = data.total_issued;
      document.getElementById("admin-stat-pending").innerText = data.pending_endorsements;
      document.getElementById("admin-stat-batches").innerText = data.total_batches;
      document.getElementById("admin-stat-students").innerText = data.total_students;
      document.getElementById("admin-stat-teachers").innerText = data.total_teachers;
      document.getElementById("admin-stat-revoked").innerText = data.total_revoked;
    }
  } catch (err) {
    console.error("Admin stats error:", err);
  }

  // 2. Fetch pending credentials
  try {
    const res = await fetch("/api/admin/pending-credentials", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      renderAdminPending(data.pending_credentials || []);
    }
  } catch (err) {
    console.error("Pending credentials error:", err);
  }

  // 3. Fetch audit logs
  try {
    const res = await fetch("/api/admin/audit-logs", {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      renderAdminAuditLogs(data.logs || []);
    }
  } catch (err) {
    console.error("Audit logs error:", err);
  }
}

function renderAdminPending(items) {
  const tbody = document.getElementById("admin-pending-tbody");
  tbody.innerHTML = "";

  const sealBtn = document.getElementById("admin-seal-batch-btn");

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-400 font-sans">No pending credentials in queue. All faculty endorsements have been sealed into Merkle tree batches.</td></tr>`;
    sealBtn.disabled = true;
    sealBtn.classList.add("opacity-50", "cursor-not-allowed");
    return;
  }

  sealBtn.disabled = false;
  sealBtn.classList.remove("opacity-50", "cursor-not-allowed");

  items.forEach(it => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="py-2.5 px-3 text-slate-800 font-bold">${it.credential_id}</td>
      <td class="py-2.5 px-3 font-sans font-semibold">${it.student_name}</td>
      <td class="py-2.5 px-3">${it.student_usn}</td>
      <td class="py-2.5 px-3 font-sans">${it.degree_type} (${it.major_specialization})</td>
      <td class="py-2.5 px-3 text-amber-600 font-bold">${it.cgpa.toFixed(2)}</td>
      <td class="py-2.5 px-3 font-sans">${it.teacher_name}</td>
      <td class="py-2.5 px-3 text-emerald-600 font-mono">${it.leaf_hash.substring(0, 16)}...</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderAdminAuditLogs(logs) {
  const list = document.getElementById("admin-audit-logs-list");
  list.innerHTML = "";

  if (logs.length === 0) {
    list.innerHTML = `<div class="p-3 text-slate-400 text-center font-sans">No audit events recorded yet.</div>`;
    return;
  }

  logs.forEach(l => {
    const div = document.createElement("div");
    div.className = "p-2 rounded bg-slate-50 border border-slate-200 flex justify-between items-center text-[11px]";
    div.innerHTML = `
      <div class="space-x-2">
        <span class="text-slate-400 font-mono">${l.timestamp}</span>
        <span class="px-1.5 py-0.5 rounded bg-slate-200 text-slate-800 font-bold text-[10px] uppercase">${l.action}</span>
        <span class="text-slate-700 font-sans">${l.details}</span>
      </div>
      <span class="text-slate-400 text-[10px] font-sans">${l.actor_name} (${l.actor_role})</span>
    `;
    list.appendChild(div);
  });
}

async function executeBatchSeal() {
  if (!confirm("Confirm Batch Seal: This will compute the Merkle Tree, sign the Merkle Root with Presidency University's ECDSA Private Key, and record the batch to the immutable ledger.")) {
    return;
  }

  showToast("Computing Merkle Tree & Signing Root with University Key...", "info");

  try {
    const res = await fetch("/api/admin/batches/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Batch sealing failed.", "error");
      return;
    }

    confetti({ particleCount: 100, spread: 80, origin: { y: 0.5 } });
    showToast(`Batch Sealed! Committed to Ledger Block #${data.block_number} with Merkle Root: ${data.merkle_root.substring(0, 12)}...`, "success");
    loadAdminDashboard();
  } catch (err) {
    showToast("Batch sealing network error.", "error");
  }
}

async function submitRevocation() {
  const credId = document.getElementById("revoke-id-input").value.trim();
  const reason = document.getElementById("revoke-reason-input").value.trim();

  if (!credId || !reason) {
    showToast("Please provide both Credential ID and revocation reason.", "warning");
    return;
  }

  if (!confirm(`Are you certain you wish to permanently revoke ${credId}? This cannot be undone on the ledger.`)) {
    return;
  }

  try {
    const res = await fetch("/api/admin/credentials/revoke", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({ credential_id: credId, reason: reason })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Revocation failed.", "error");
      return;
    }

    showToast(`Credential ${credId} has been revoked on the public registry.`, "warning");
    document.getElementById("revoke-id-input").value = "";
    document.getElementById("revoke-reason-input").value = "";
    loadAdminDashboard();
  } catch (err) {
    showToast("Revocation network error.", "error");
  }
}

// -----------------------------------------------------------------------------
// 10. Ledger Explorer & University Identity
// -----------------------------------------------------------------------------

async function loadLedgerBlocks() {
  const container = document.getElementById("ledger-blocks-container");
  if (!container) return;

  try {
    const res = await fetch("/api/ledger/blocks");
    if (res.ok) {
      const data = await res.json();
      const blocks = data.blocks || [];
      container.innerHTML = "";

      if (blocks.length === 0) {
        container.innerHTML = `<div class="p-6 text-center text-slate-400">No blocks found on ledger.</div>`;
        return;
      }

      blocks.forEach(b => {
        const div = document.createElement("div");
        div.className = "p-4 bg-slate-900 text-slate-200 rounded-xl border border-slate-800 space-y-3 font-mono text-xs";
        div.innerHTML = `
          <div class="flex flex-wrap justify-between items-center gap-2 border-b border-slate-800 pb-2 font-sans">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              <h4 class="font-bold text-sm text-white">Block #${b.block_number}</h4>
              <span class="text-xs text-amber-400 font-mono">${b.batch_id}</span>
            </div>
            <div class="text-[11px] text-slate-400">
              <i class="fa-regular fa-clock mr-1"></i> ${b.created_at}
            </div>
          </div>
          <div>
            <span class="text-slate-500 block text-[10px]">Batch Merkle Root (SHA-256):</span>
            <div class="text-amber-300 break-all">${b.merkle_root}</div>
          </div>
          <div>
            <span class="text-slate-500 block text-[10px]">University ECDSA SECP256k1 Signature:</span>
            <div class="text-slate-400 break-all text-[11px]">${b.signature}</div>
          </div>
          <div class="flex justify-between items-center text-[10px] text-slate-400 pt-1 border-t border-slate-800 font-sans">
            <span>Certificates Sealed in Batch: <strong class="text-emerald-400 font-mono">${b.total_credentials}</strong></span>
            <span>Issuer: <strong class="text-slate-300 font-mono">${b.university_did}</strong></span>
          </div>
        `;
        container.appendChild(div);
      });
    }
  } catch (err) {
    console.error("Ledger blocks error:", err);
  }
}

async function loadUniversityIdentity() {
  try {
    const res = await fetch("/api/admin/university-identity");
    if (res.ok) {
      const data = await res.json();
      const didEl = document.getElementById("univ-identity-did");
      const pemEl = document.getElementById("univ-public-key-pem");
      const jsonEl = document.getElementById("univ-did-document-json");

      if (didEl) didEl.innerText = data.did;
      if (pemEl) pemEl.innerText = data.public_key_pem;
      if (jsonEl) jsonEl.innerText = JSON.stringify(data.did_document, null, 2);
    }
  } catch (err) {
    console.error("University identity error:", err);
  }
}
