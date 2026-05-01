(function () {

const scriptTag = document.currentScript;

const BASE_URL = "https://chatbot.janzarieldiaz.com";
const USE_KB = scriptTag.getAttribute("data-use-kb") === "true";
const TITLE = scriptTag.getAttribute("data-title") || "Assistant";

// ------------------------
// LOAD CSS
// ------------------------
const css = document.createElement("link");
css.rel = "stylesheet";
css.href = `${BASE_URL}/static/widget.css`;
document.head.appendChild(css);

// ------------------------
// WIDGET HTML
// ------------------------
const widget = document.createElement("div");
widget.innerHTML = `
<div id="chatbot-launcher">💬</div>

<div id="chatbot-bubble-preview">Ask about privacy policy 👇</div>

<div id="chatbot-box">
    <div id="chatbot-header">
        ${TITLE}
        <span id="chatbot-close">✕</span>
    </div>

    <div id="chatbot-messages"></div>

    <div id="chatbot-input-area">
        <input id="chatbot-input" placeholder="Type message..." />
        <button id="chatbot-send">➤</button>
    </div>
</div>
`;

document.body.appendChild(widget);

// ------------------------
// ELEMENTS
// ------------------------
const launcher = document.getElementById("chatbot-launcher");
const box = document.getElementById("chatbot-box");
const close = document.getElementById("chatbot-close");
const messages = document.getElementById("chatbot-messages");
const bubble = document.getElementById("chatbot-bubble-preview");
// ------------------------
// INITIAL MESSAGE
// ------------------------
function addInitialMessage() {
    setTimeout(() => {
        addBotMessage("👋 Hi! Do you have any questions about the Privacy Policy?");
    }, 600);
}

// ------------------------
// OPEN CHAT
// ------------------------
launcher.onclick = () => {
    box.classList.add("open");
    launcher.classList.remove("pulse");
    bubble.style.display = "none";
};

// ------------------------
// CLOSE CHAT
// ------------------------
close.onclick = () => {
    box.classList.remove("open");
    launcher.classList.add("pulse");
    bubble.style.display = "block";
};

// ------------------------
// MESSAGE UI
// ------------------------
function addUserMessage(text) {
    const div = document.createElement("div");
    div.className = "user message";
    div.textContent = text;
    messages.appendChild(div);
    scroll();
}

function addBotMessage(text) {
    const div = document.createElement("div");
    div.className = "bot message";
    div.innerHTML = text;
    messages.appendChild(div);
    scroll();
}

// ------------------------
// LOADING ANIMATION
// ------------------------
function showLoading() {
    const div = document.createElement("div");
    div.className = "bot message loading";
    div.id = "loading";
    div.innerHTML = `<span></span><span></span><span></span>`;
    messages.appendChild(div);
    scroll();
}

function hideLoading() {
    const el = document.getElementById("loading");
    if (el) el.remove();
}

// ------------------------
// SEND MESSAGE
// ------------------------
async function sendMessage() {
    const input = document.getElementById("chatbot-input");
    const msg = input.value.trim();
    if (!msg) return;

    addUserMessage(msg);
    input.value = "";

    showLoading();

    const res = await fetch(`${BASE_URL}/chat`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            message: msg,
            use_kb: USE_KB
        })
    });

    const data = await res.json();

    hideLoading();
    addBotMessage(data.reply);
    }

// ------------------------
// EVENTS
// ------------------------
document.getElementById("chatbot-send").onclick = sendMessage;

document.getElementById("chatbot-input")
.addEventListener("keypress", e => {
    if (e.key === "Enter") sendMessage();
});

function scroll() {
    messages.scrollTop = messages.scrollHeight;
}

// ------------------------
// INIT
// ------------------------
launcher.classList.add("pulse");
bubble.style.display = "block";
addInitialMessage();

})();