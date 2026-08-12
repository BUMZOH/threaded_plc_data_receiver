const statusElement = document.getElementById("status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");
const dataSelect = document.getElementById("data-select");
const chartDataElement = document.getElementById("chart-data");
const chartCanvas = document.getElementById("data-chart");

let isChartBusy = false;

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
    const dataNames = await pywebview.api.get_data_names();
    setDataNames(dataNames);

    const result = await pywebview.api.get_status();
    updateStatus(result);
});

