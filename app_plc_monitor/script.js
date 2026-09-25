const statusElement = document.getElementById("status");
const plcIpElement = document.getElementById("plc-ip");
const communicationStatusElement = document.getElementById("communication-status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");
const saveModeSelect = document.getElementById("save-mode-select");
const dataSelect = document.getElementById("data-select");
const chartDataElement = document.getElementById("chart-data");

const judgeResultElement = document.getElementById("judge-result");
const measuredAtElement = document.getElementById("measured-at");
const oldestButton = document.getElementById("oldest-button");
const previousButton = document.getElementById("previous-button");
const nextButton = document.getElementById("next-button");
const latestButton = document.getElementById("latest-button");

const statusBadge = document.querySelector(".status-badge");

const chartCanvas = document.getElementById("data-chart");

let isChartBusy = false;
let currentRecordKey = null;

const dataChart = new Chart(chartCanvas, {
    type: "line",
    data: {
        labels: [],
        datasets: [
            {
                label: "計測値",
                data: [],
                borderWidth: 1,
                pointRadius: 2,
            },
        ],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        normalized: true,
        scales: {
            x: {
                title: {
                    display: true,
                    text: "測定点",
                },
                ticks: {
                    maxTicksLimit: 11,
                },
            },
            y: {
                title: {
                    display: true,
                    text: "計測値",
                },
            },
        },
        plugins: {
            legend : {
                display: false,
            },
        },
    },
});

function setDataNames(dataNames) {
    for (const dataName of dataNames) {
        const option = document.createElement("option");

        option.value = dataName;
        option.textContent = dataName;

        dataSelect.appendChild(option);
    }
}

function updateHistoryButtons(isRunning) {
    const isDisabled = (
        isRunning
        || dataSelect.value === "all"
    );

    oldestButton.disabled = isDisabled;
    previousButton.disabled = isDisabled;
    nextButton.disabled = isDisabled;
    latestButton.disabled = isDisabled;
}

window.receiveStatus = function (message) {
    communicationStatusElement.textContent = message;
}

window.receiveData = function (payload) {
    const selectedDataName = dataSelect.value;

    if (
        selectedDataName !== "all"
        && selectedDataName !== payload.data_name
    ) {
        return;
    }

    if (isChartBusy) {
        console.log(
            `グラフ描画中のため受信データを無視: ${payload.data_name}`
        );
        return;
    }

    isChartBusy = true;

    try {
        const values = payload.values;

        // 受信データの点数に合わせてX軸を作る
        dataChart.data.labels = values.map(
            (_, index) => index + 1
        );

        dataChart.data.datasets[0].data = values;
        dataChart.data.datasets[0].label = payload.data_name;

        chartDataElement.textContent = payload.data_name;
        judgeResultElement.textContent = payload.judge ?? "-";
        measuredAtElement.textContent = payload.measured_at;

        // 判定色変更用
        judgeResultElement.classList.toggle("ok", payload.judge === "OK");
        judgeResultElement.classList.toggle("ng", payload.judge === "NG");

        //--------------
        const startTime = performance.now();
        //--------------

        dataChart.update("none");

        requestAnimationFrame(() => {

            //--------------
            const elapsedTime = performance.now() - startTime;
            console.log(
                `グラフ描画時間: ${elapsedTime.toFixed(2)} ms`
            );
            //--------------

            isChartBusy = false;
        });

    } catch (error) {
        isChartBusy = false;
        console.error(error);
    }

};

function updateStatus(result) {
    statusElement.textContent = result.message;

    const isRunning = result.status === "running";
    
    statusBadge.classList.toggle(
        "running",
        isRunning
    );

    startButton.disabled = isRunning;
    stopButton.disabled = !isRunning;
    saveModeSelect.disabled = isRunning;

    updateHistoryButtons(isRunning);
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

        communicationStatusElement.textContent = "---";
    } catch (error) {
        console.error(error);
        statusElement.textContent = "停止エラー";
    }
}

async function showSavedData(direction){
    try {
        const dataName = dataSelect.value;

        const result = await pywebview.api.get_saved_data(
            dataName,
            direction,
            currentRecordKey
        );
        
        if (result === null) {
            return;
        }

        currentRecordKey = result.id;

        window.receiveData(result);

    } catch (error) {
        console.error(error);
    }
}


startButton.addEventListener("click", startMonitoring);
stopButton.addEventListener("click", stopMonitoring);


oldestButton.addEventListener(
    "click",
    () => showSavedData("oldest")
);

previousButton.addEventListener(
    "click",
    () => showSavedData("previous")
);

nextButton.addEventListener(
    "click",
    () => showSavedData("next")
);

latestButton.addEventListener(
    "click",
    () => showSavedData("latest")
);

saveModeSelect.addEventListener("change", async () => {
    try {
        await pywebview.api.set_save_mode(saveModeSelect.value);

        currentRecordKey = null;
        measuredAtElement.textContent = "";
    } catch (error) {
        console.error(error);
    }
});

dataSelect.addEventListener("change", async () => {
    currentRecordKey = null;
    measuredAtElement.textContent = "";

    const result = await pywebview.api.get_status();
    updateHistoryButtons(result.status === "running");
});

window.addEventListener("pywebviewready", async () => {
    const plcIpAddress = await pywebview.api.get_plc_ip_address();
    plcIpElement.textContent = plcIpAddress;

    const dataNames = await pywebview.api.get_data_names();
    setDataNames(dataNames);

    const result = await pywebview.api.get_status();
    updateStatus(result);
});

