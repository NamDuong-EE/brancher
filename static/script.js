const loadBtn = document.getElementById("loadBtn");
const tokenInput = document.getElementById("tokenInput");
const statusDiv = document.getElementById("statusMessage");

let currentToken = "";

function setStatus(msg, ok = true) {
    statusDiv.style.display = "block";
    statusDiv.className = `status-message ${ok ? 'success' : 'error'}`;
    statusDiv.textContent = msg;
    setTimeout(() => {
        statusDiv.style.display = "none";
    }, 4000);
}

async function loadConfig() {
    const token = tokenInput.value.trim();
    if (!token) {
        setStatus("Please enter API token first", false);
        return;
    }

    currentToken = token;

    try {
        // Show loading state
        loadBtn.disabled = true;
        loadBtn.textContent = "Loading...";

        const response = await fetch("/config", {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + token
            }
        });

        if (response.status === 401) {
            setStatus("Unauthorized - Invalid token", false);
            loadBtn.disabled = false;
            loadBtn.textContent = "Authenticate & Load";
            return;
        }

        const data = await response.json();

        // Success - trigger UI update
        if (window.onConfigLoaded) {
            window.onConfigLoaded(data);
        }

        setStatus("? Configuration loaded successfully", true);
        loadBtn.textContent = "? Authenticated";

        // Change button to reload
        setTimeout(() => {
            loadBtn.textContent = "Reload Config";
            loadBtn.disabled = false;
        }, 2000);

    } catch (err) {
        setStatus("Failed to load: " + err.message, false);
        loadBtn.disabled = false;
        loadBtn.textContent = "Authenticate & Load";
    }
}

async function saveConfig(configData) {
    const token = currentToken || tokenInput.value.trim();

    if (!token) {
        setStatus("Please authenticate first", false);
        return;
    }

    if (!configData) {
        setStatus("No config data to save", false);
        return;
    }

    try {
        const response = await fetch("/config", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(configData)
        });

        if (response.status === 401) {
            setStatus("Unauthorized", false);
            return;
        }

        if (response.status === 415) {
            setStatus("Invalid JSON format", false);
            return;
        }

        const result = await response.json();

        if (result.status === "ok") {
            setStatus("Configuration saved successfully", true);

            // Reload config to reflect changes
            setTimeout(() => {
                loadConfig();
            }, 1000);
        } else {
            setStatus("Server error: " + JSON.stringify(result), false);
        }

    } catch (err) {
        setStatus("Failed to save: " + err.message, false);
    }
}

// Expose functions globally
window.loadConfig = loadConfig;
window.saveConfig = saveConfig;

// Event listeners
loadBtn.addEventListener("click", loadConfig);

// Allow Enter key to authenticate
tokenInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        loadConfig();
    }
});

// Auto-fill token if in development
if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    // Uncomment below line for quick testing
    // tokenInput.value = "admin";
}
