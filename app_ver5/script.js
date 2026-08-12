const statusElement = document.getElementById("status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");
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
                pointRadius: 0,
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

window.receiveData = function (payload) {
    if (isChartBusy) {
        console.log(
            `グラフ描画中のため受信データを無視: ${payload.data_name}`
        );
        return;
    }

    isChartBusy = true;

    try {
        const values = payload.values;

        // 1000点のX軸を作る
        dataChart.data.labels = values.map(
            (_, index) => index + 1
        );

        dataChart.data.datasets[0].data = values;
        dataChart.data.datasets[0].label = payload.data_name;

        chartDataElement.textContent = payload.data_name;

        dataChart.update("none");

        requestAnimationFrame(() => {
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
    const result = await pywebview.api.get_status();
    updateStatus(result);
});

