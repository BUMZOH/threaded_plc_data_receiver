let waveChart = null;
let records = [];
let currentIndex = -1;


window.addEventListener("pywebviewready", initialize);

document.getElementById("loadButton").addEventListener("click", loadData);
document.getElementById("previousButton").addEventListener("click", showPrevious);
document.getElementById("nextButton").addEventListener("click", showNext);
document.getElementById("applyAxisButton").addEventListener("click", applyAxis);
document.getElementById("resetAxisButton").addEventListener("click", resetAxis);


async function initialize() {
    const options = await window.pywebview.api.get_filter_options();

    const dataNameSelect = document.getElementById("dataName");

    for (const dataName of options.data_names) {
        const option = document.createElement("option");
        option.value = dataName;
        option.textContent = dataName;
        dataNameSelect.appendChild(option);
    }

    document.getElementById("startAt").value =
        sqliteDateTimeToInput(options.min_measured_at);

    document.getElementById("endAt").value =
        sqliteDateTimeToInput(options.max_measured_at);

    createChart();
    updateNavigation();
}


function createChart() {
    const context = document.getElementById("waveChart");

    waveChart = new Chart(context, {
        type: "line",
        data: {
            datasets: [
                {
                    label: "data",
                    data: [],
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            parsing: false,
            normalized: true,
            elements: {
                point: {
                    radius: 2,
                },
                line: {
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    type: "linear",
                    title: {
                        display: true,
                        text: "Sample",
                    },
                },
                y: {
                    title: {
                        display: true,
                        text: "Value",
                    },
                },
            },
        },
    });
}


async function loadData() {
    const dataName = document.getElementById("dataName").value;
    const judge = document.getElementById("judge").value;
    const startAt = inputDateTimeToSqlite(
        document.getElementById("startAt").value
    );
    const endAt = inputDateTimeToSqlite(
        document.getElementById("endAt").value
    );

    if (!dataName || !startAt || !endAt) {
        setStatus("検索条件を入力してください。");
        return;
    }

    if (startAt > endAt) {
        setStatus("開始日時は終了日時以前にしてください。");
        return;
    }

    const result = await window.pywebview.api.load_data(
        dataName,
        judge,
        startAt,
        endAt,
    );

    records = result.records;

    if (records.length === 0) {
        currentIndex = -1;
        clearChart();
        updateRecordInfo();
        updateNavigation();
        setStatus("該当データはありません。");
        return;
    }

    currentIndex = 0;
    showCurrentRecord();
    setStatus(`${records.length} 件見つかりました。`);
}


function showPrevious() {
    if (currentIndex <= 0) {
        return;
    }

    currentIndex -= 1;
    showCurrentRecord();
}


function showNext() {
    if (currentIndex < 0 || currentIndex >= records.length - 1) {
        return;
    }

    currentIndex += 1;
    showCurrentRecord();
}


function showCurrentRecord() {
    if (currentIndex < 0 || currentIndex >= records.length) {
        return;
    }

    const record = records[currentIndex];

    waveChart.data.datasets[0].label =
        `${record.data_name} / ${record.measured_at} / ${record.judge}`;

    waveChart.data.datasets[0].data =
        record.values.map((value, index) => ({
            x: index,
            y: value,
        }));

    waveChart.update("none");

    updateRecordInfo();
    updateNavigation();
}


function clearChart() {
    waveChart.data.datasets[0].label = "data";
    waveChart.data.datasets[0].data = [];
    waveChart.update("none");
}


function updateRecordInfo() {
    if (currentIndex < 0 || currentIndex >= records.length) {
        document.getElementById("recordId").textContent = "id: -";
        document.getElementById("measuredAt").textContent =
            "measured_at: -";
        document.getElementById("recordJudge").textContent = "judge: -";
        return;
    }

    const record = records[currentIndex];

    document.getElementById("recordId").textContent =
        `id: ${record.id}`;

    document.getElementById("measuredAt").textContent =
        `measured_at: ${record.measured_at}`;

    document.getElementById("recordJudge").textContent =
        `judge: ${record.judge}`;
}


function updateNavigation() {
    const previousButton = document.getElementById("previousButton");
    const nextButton = document.getElementById("nextButton");
    const position = document.getElementById("position");

    if (records.length === 0 || currentIndex < 0) {
        position.textContent = "0 / 0 件";
        previousButton.disabled = true;
        nextButton.disabled = true;
        return;
    }

    position.textContent =
        `${currentIndex + 1} / ${records.length} 件`;

    previousButton.disabled = currentIndex === 0;
    nextButton.disabled = currentIndex === records.length - 1;
}


function applyAxis() {
    waveChart.options.scales.x.min = numberOrUndefined("xMin");
    waveChart.options.scales.x.max = numberOrUndefined("xMax");
    waveChart.options.scales.y.min = numberOrUndefined("yMin");
    waveChart.options.scales.y.max = numberOrUndefined("yMax");

    waveChart.update("none");
}


function resetAxis() {
    for (const id of ["xMin", "xMax", "yMin", "yMax"]) {
        document.getElementById(id).value = "";
    }

    delete waveChart.options.scales.x.min;
    delete waveChart.options.scales.x.max;
    delete waveChart.options.scales.y.min;
    delete waveChart.options.scales.y.max;

    waveChart.update("none");
}


function numberOrUndefined(id) {
    const value = document.getElementById(id).value;

    if (value === "") {
        return undefined;
    }

    return Number(value);
}


function sqliteDateTimeToInput(value) {
    if (!value) {
        return "";
    }

    return value.replace(" ", "T");
}


function inputDateTimeToSqlite(value) {
    if (!value) {
        return "";
    }

    return value.replace("T", " ");
}


function setStatus(message) {
    document.getElementById("status").textContent = message;
}
