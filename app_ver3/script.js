const statusElement = document.getElementById("status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");


function updateStatus(result) {
    statusElement.textContent = result.message;

    const isRunning = result.status === "running";

    startButton.disabled = isRunning;
    stopButton.disabled = !isRunning;
}


async function  startMonitoring() {
    try {
        const result = await pywebview.api.start_monitoring();
        updateStatus(result);
    } catch (error) {
        console.error(error);
        statusElement.textContent = "開始エラー";
    }
}


async function stopMonitoring() {
    try {
        const result = await pywebview.api.stop_monitoring();
        updateStatus(result);
    } catch (error) {
        console.error(error);
        statusElement.textContent = "停止エラー";
    }
}


startButton.addEventListener("click", startMonitoring);
stopButton.addEventListener("click", stopMonitoring);

window.addEventListener("pywebviewready", async () => {
    const result = await pywebview.api.get_status();
    updateStatus(result);
});

