import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";

const state = {
  auth: null,
  currentUser: null,
  currentConversationId: null,
  conversations: [],
  firebaseEnabled: false,
  googleProvider: null,
};

const elements = {
  appFrame: document.querySelector(".app-frame"),
  authPanel: document.getElementById("auth-panel"),
  authStatus: document.getElementById("auth-status"),
  chatForm: document.getElementById("chat-form"),
  chatPanel: document.getElementById("chat-panel"),
  conversationCount: document.getElementById("conversation-count"),
  conversationList: document.getElementById("conversation-list"),
  conversationTitle: document.getElementById("conversation-title"),
  documentFile: document.getElementById("document-file"),
  documentLabel: document.getElementById("document-label"),
  documentPill: document.getElementById("document-pill"),
  googleAuthButton: document.getElementById("google-auth-btn"),
  logoutButton: document.getElementById("logout-btn"),
  messageInput: document.getElementById("message-input"),
  messageList: document.getElementById("message-list"),
  newConversationButton: document.getElementById("new-conversation-btn"),
  sendButton: document.getElementById("send-btn"),
  sidebar: document.getElementById("sidebar"),
  sidebarStatus: document.getElementById("sidebar-status"),
  uploadForm: document.getElementById("upload-form"),
  userEmail: document.getElementById("user-email"),
};

async function init() {
  const response = await fetch("/api/frontend-config");
  const config = await response.json();
  state.firebaseEnabled = config.firebase_enabled;

  if (!config.firebase_enabled) {
    setStatus(elements.authStatus, "Firebase is not configured yet. Add the .env values and restart the server.");
    return;
  }

  const app = initializeApp(config.firebase);
  state.auth = getAuth(app);
  state.googleProvider = new GoogleAuthProvider();
  state.googleProvider.setCustomParameters({ prompt: "select_account" });

  onAuthStateChanged(state.auth, async (user) => {
    state.currentUser = user;
    elements.userEmail.textContent = user?.email || "Signed out";
    toggleSignedInView(Boolean(user));

    if (!user) {
      state.currentConversationId = null;
      state.conversations = [];
      renderConversationList();
      clearMessages();
      return;
    }

    setStatus(elements.authStatus, "");
    try {
      await refreshConversations();
    } catch (error) {
      setStatus(elements.sidebarStatus, error.message);
    }
  });

  wireEvents();
  clearMessages();
}

function wireEvents() {
  elements.googleAuthButton.addEventListener("click", authenticateWithGoogle);
  elements.logoutButton.addEventListener("click", async () => {
    await signOut(state.auth);
  });
  elements.newConversationButton.addEventListener("click", async () => {
    await createConversation();
  });
  elements.uploadForm.addEventListener("submit", handleUpload);
  elements.chatForm.addEventListener("submit", handleSendMessage);
  elements.messageInput.addEventListener("keydown", handleComposerKeydown);
}

function handleComposerKeydown(event) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }

  event.preventDefault();
  elements.chatForm.requestSubmit();
}

async function authenticateWithGoogle() {
  elements.googleAuthButton.disabled = true;
  setStatus(elements.authStatus, "Opening Google sign-in...");

  try {
    await signInWithPopup(state.auth, state.googleProvider);
    setStatus(elements.authStatus, "");
  } catch (error) {
    setStatus(elements.authStatus, humanizeFirebaseError(error));
  } finally {
    elements.googleAuthButton.disabled = false;
  }
}

async function createConversation() {
  try {
    const conversation = await apiFetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: null }),
    });
    state.currentConversationId = conversation.id;
    await refreshConversations();
    await loadConversation(conversation.id);
    setStatus(elements.sidebarStatus, "Created a new empty conversation.");
  } catch (error) {
    setStatus(elements.sidebarStatus, error.message);
  }
}

async function handleUpload(event) {
  event.preventDefault();
  if (!elements.documentFile.files.length) {
    setStatus(elements.sidebarStatus, "Pick a PDF or DOCX file first.");
    return;
  }

  const uploadButton = elements.uploadForm.querySelector("button");
  uploadButton.disabled = true;
  setStatus(elements.sidebarStatus, "Indexing document...");

  try {
    let conversationId = state.currentConversationId;
    if (!conversationId) {
      const conversation = await apiFetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: null }),
      });
      conversationId = conversation.id;
      state.currentConversationId = conversationId;
    }

    const formData = new FormData();
    formData.append("conversation_id", conversationId);
    formData.append("file", elements.documentFile.files[0]);

    const payload = await apiFetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    await refreshConversations();
    await loadConversation(payload.conversation_id);
    setStatus(elements.sidebarStatus, `Indexed ${payload.filename} into ${payload.chunk_count} chunks.`);
    elements.uploadForm.reset();
  } catch (error) {
    setStatus(elements.sidebarStatus, error.message);
  } finally {
    uploadButton.disabled = false;
  }
}

async function handleSendMessage(event) {
  event.preventDefault();
  const message = elements.messageInput.value.trim();
  if (!message) {
    return;
  }
  if (!state.currentConversationId) {
    setStatus(elements.sidebarStatus, "Create or select a conversation before sending a message.");
    return;
  }

  elements.sendButton.disabled = true;
  setStatus(elements.sidebarStatus, "Generating answer...");

  try {
    const response = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.currentConversationId,
        message,
      }),
    });

    appendMessage({ role: "user", content: message, sources: [] });
    appendMessage({ role: "assistant", content: response.answer, sources: response.sources });
    elements.messageInput.value = "";
    setStatus(elements.sidebarStatus, "");
    await refreshConversations();
  } catch (error) {
    setStatus(elements.sidebarStatus, error.message);
  } finally {
    elements.sendButton.disabled = false;
  }
}

async function refreshConversations() {
  const conversations = await apiFetch("/api/conversations");
  state.conversations = conversations;
  renderConversationList();

  if (!state.currentConversationId && conversations.length) {
    await loadConversation(conversations[0].id);
  }
}

function renderConversationList() {
  elements.conversationList.innerHTML = "";
  elements.conversationCount.textContent = String(state.conversations.length).padStart(2, "0");

  for (const conversation of state.conversations) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = conversation.id === state.currentConversationId ? "active" : "";
    button.addEventListener("click", async () => {
      try {
        await loadConversation(conversation.id);
      } catch (error) {
        setStatus(elements.sidebarStatus, error.message);
      }
    });

    const title = document.createElement("div");
    title.className = "conversation-list__title";
    title.textContent = conversation.title;

    const meta = document.createElement("div");
    meta.className = "conversation-list__meta";
    meta.textContent = conversation.document_name || "No document uploaded";

    button.append(title, meta);
    item.append(button);
    elements.conversationList.append(item);
  }
}

async function loadConversation(conversationId) {
  const detail = await apiFetch(`/api/conversations/${conversationId}`);
  state.currentConversationId = conversationId;
  renderConversationList();
  clearMessages();

  const hasDocument = Boolean(detail.conversation.document_name);
  elements.conversationTitle.textContent = detail.conversation.title;
  elements.documentLabel.textContent =
    detail.conversation.document_name || "Upload a document to start chatting.";
  elements.documentPill.textContent = hasDocument
    ? (detail.conversation.document_type || "document").toUpperCase()
    : "No document";

  for (const message of detail.messages) {
    appendMessage(message);
  }

  if (!detail.messages.length) {
    renderEmptyState(
      hasDocument ? "Document indexed and ready" : "This conversation has no document yet",
      hasDocument
        ? "Ask a question below and the backend will retrieve the most relevant chunks before generating an answer."
        : "Upload one PDF or DOCX from the sidebar to activate grounded retrieval for this conversation.",
    );
  }
}

function clearMessages() {
  elements.messageList.innerHTML = "";
  elements.conversationTitle.textContent = "Choose a conversation";
  elements.documentLabel.textContent = "Upload a document to start chatting.";
  elements.documentPill.textContent = "No document";
  renderEmptyState(
    "Start with a saved conversation",
    "Create a new conversation or open an older one from the left sidebar, upload one PDF or DOCX, then ask questions about that document.",
  );
}

function appendMessage(message) {
  removeEmptyState();

  const article = document.createElement("article");
  article.className = `message message--${message.role}`;

  const role = document.createElement("div");
  role.className = "message__role";
  role.textContent = message.role === "assistant" ? "Assistant" : "You";

  const body = document.createElement("div");
  body.className = "message__body";
  body.textContent = message.content;

  article.append(role, body);

  elements.messageList.append(article);
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderEmptyState(title, description) {
  removeEmptyState();

  const article = document.createElement("article");
  article.className = "empty-state";
  article.dataset.emptyState = "true";

  const heading = document.createElement("h3");
  heading.textContent = title;

  const copy = document.createElement("p");
  copy.textContent = description;

  article.append(heading, copy);
  elements.messageList.append(article);
}

function removeEmptyState() {
  const emptyState = elements.messageList.querySelector("[data-empty-state='true']");
  if (emptyState) {
    emptyState.remove();
  }
}

function toggleSignedInView(isSignedIn) {
  elements.authPanel.classList.toggle("hidden", isSignedIn);
  elements.chatPanel.classList.toggle("hidden", !isSignedIn);
  elements.sidebar.classList.toggle("hidden", !isSignedIn);
  elements.appFrame.classList.toggle("app-frame--signed-in", isSignedIn);
  elements.appFrame.classList.toggle("app-frame--signed-out", !isSignedIn);
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const user = state.auth.currentUser;
  if (!user) {
    throw new Error("You must be signed in.");
  }

  const token = await user.getIdToken();
  headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = "Request failed.";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_error) {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.json();
}

function humanizeFirebaseError(error) {
  const code = error?.code || "";

  if (code === "auth/popup-closed-by-user") {
    return "Google sign-in was closed before completion.";
  }
  if (code === "auth/popup-blocked") {
    return "The browser blocked the Google sign-in popup. Allow popups for this site and try again.";
  }
  if (code === "auth/operation-not-allowed") {
    return "Google sign-in is not enabled in Firebase Authentication for this project.";
  }
  if (code === "auth/unauthorized-domain") {
    return "This domain is not authorized in Firebase. Add it in the Firebase Authentication settings.";
  }

  return error?.message || "Google sign-in failed.";
}

function setStatus(target, text) {
  target.textContent = text;
}

init().catch((error) => {
  setStatus(elements.authStatus, error.message);
});
