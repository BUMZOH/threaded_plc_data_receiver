const statusElement = document.getElementById("status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");
const chartMotorElement = document.getElementById("chart-motor");
const chartCanvas = document.getElementById("motor-current-chart");

let isChartBusy = false;

const motorCurrentChart = new Chart(chartCanvas, {
    type: "line",
    data: {
        labels: [],
        datasets: [
            {
                label: "モータ電流値",
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
                    text: "電流値",
                },
            },
        },
        plugins: {
            legend: {
                display: false,
            },
        },
    },
});


function updateStatus(result) {
    statusElement.textContent = result.message;

    const isRunning = result.status === "running";

    startButton.disabled = isRunning;
    stopButton.disabled = !isRunning;
}


window.receiveMotorData = function (payload) {
    // 前回のグラフ更新処理中なら、今回の通知は捨てる。
    if (isChartBusy) {
        console.log(
            `グラフ描画中のため受信データを無視: ${payload.motor_name}`
        );
        return;
    }

    isChartBusy = true;

    try {
        const values = payload.values;

        motorCurrentChart.data.labels = values.map(
            (_, index) => index + 1
        );
        motorCurrentChart.data.datasets[0].data = values;
        motorCurrentChart.data.datasets[0].label = payload.motor_name;

        chartMotorElement.textContent = payload.motor_name;

        // アニメーションなしで即時更新する。
        motorCurrentChart.update("none");

        // 次の描画フレームまでbusyを維持する。
        // この間に届いた次のPush通知は上の判定で捨てる。
        requestAnimationFrame(() => {
            isChartBusy = false;
        });
    } catch (error) {
        isChartBusy = false;
        console.error(error);
    }
};


async function startMonitoring() {
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
