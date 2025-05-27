// app/static/js/main.js
async function sendMessage() {
    const messageInput = document.getElementById("message");
    const message = messageInput.value;
    const responseArea = document.getElementById("response");

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: message })
        });
        const data = await res.json();
        responseArea.innerText = data.response;
    } catch (error) {
        responseArea.innerText = "An error occurred while sending the message.";
    }
}
