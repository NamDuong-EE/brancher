const loadBtn = document.getElementById("loadBtn");
const saveBtn = document.getElementById("saveBtn");
const tokenInput = document.getElementById("token");
const configArea = document.getElementById("configArea");
const statusDiv = document.getElementById("status");

function setStatus(msg, ok=true){
  statusDiv.style.color = ok ? "green" : "red";
  statusDiv.textContent = msg;
  setTimeout(()=>{ statusDiv.textContent = ""; }, 4000);
}

async function loadConfig(){
  const token = tokenInput.value.trim();
  if(!token){ setStatus("enter token before load", false); return; }
  try {
    const r = await fetch("/config", {
      method: "GET",
      headers: { "Authorization": "Bearer " + token }
    });
    if(r.status === 401){ setStatus("Unauthorized", false); return; }
    const data = await r.json();
    configArea.value = JSON.stringify(data, null, 2);
    setStatus("Successfully loaded");
  } catch(err){
    setStatus("Failed while loading: " + err.message, false);
  }
}

async function saveConfig(){
  const token = tokenInput.value.trim();
  if(!token){ setStatus("Enter token before save", false); return; }
  let json;
  try {
    json = JSON.parse(configArea.value);
  } catch(e){
    setStatus("Error: Content-Type must be application/json", false);
    return;
  }
  try {
    const r = await fetch("/config", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(json)
    });
    if(r.status === 401){ setStatus("Unauthorized", false); return; }
    if(r.status === 415){ setStatus("Content-Type sai", false); return; }
    const res = await r.json();
    if(res.status === "ok") setStatus("Config saved successfully");
    else setStatus("Server return: " + JSON.stringify(res), false);
  } catch(err){
    setStatus("Failed while saving : " + err.message, false);
  }
}

loadBtn.addEventListener("click", loadConfig);
saveBtn.addEventListener("click", saveConfig);
