let waveChart = null;
let records = [];
let currentIndex = -1;


window.addEventListener("pywebviewready", initialize);

document.getElementById("loadButton").addEventListener("click", loadData);

document.getElementById("firstButton").addEventListener("click", showFirst);
document.getElementById("previousButton").addEventListener("click", showPrevious);
document.getElementById("nextButton").addEventListener("click", showNext);
document.getElementById("lastButton").addEventListener("click", showLast);
document.getElementById("positionInput").addEventListener("keydown", jumpToPosition);

document.getElementById("applyAxisButton").addEventListener("click", applyAxis);
document.getElementById("resetAxisButton").addEventListener("click", resetAxis);

document.getElementById("analysisFunction").addEventListener("change", analyzeCurrentRecord);
document.getElementById("csvOutputButton").addEventListener("click", outputAnalysisCsv);

document.getElementById("dataSource").addEventListener("change", updateFilterOptions);


async function initialize() {
    const dataSource = document.getElementById("dataSource").value;
    const analysisFunctions = await window.pywebview.api.get_analysis_functions();

    let options;
    try {
        options = await window.pywebview.api.get_filter_options(dataSource);
    } catch {
        setStatus("ローカルデータベースが見つかりません。");
        options = {
            data_names: [],
            min_measured_at: null,
            max_measured_at: null,
        };
    }

    const dataNameSelect = document.getElementById("dataName");
    for (const dataName of options.data_names) {
        const option = document.createElement("option");
        option.value = dataName;
        option.textContent = dataName;
        dataNameSelect.appendChild(option);
    }

    const analysisFunctionSelect = document.getElementById("analysisFunction");
    for (const functionName of analysisFunctions) {
        const option = document.createElement("option");
        option.value = functionName;
        option.textContent = functionName;
        analysisFunctionSelect.appendChild(option);
    }

    document.getElementById("startAt").value =
        sqliteDateTimeToInput(options.min_measured_at);

    document.getElementById("endAt").value =
        sqliteDateTimeToInput(options.max_measured_at);

    createChart();
    updateNavigation();
}

async function updateFilterOptions() {
    const dataSource = document.getElementById("dataSource").value;

    let options;

    try {
        options = await window.pywebview.api.get_filter_options(
            dataSource,
        );
    } catch {
        setStatus("データ取得元に接続できません。");
        return;
    }

    const dataNameSelect = document.getElementById("dataName");

    dataNameSelect.innerHTML = "";

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
    const dataSource = document.getElementById("dataSource").value;
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
        dataSource,
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
    
    if (dataSource === "local") {
        setStatus(`${records.length} 件見つかりました。(最大10000件・ローカル時)`);
    } else {
        setStatus(`${records.length} 件見つかりました。`);
    }
}

function showFirst() {
    if (records.length === 0) {
        return;
    }

    currentIndex = 0;
    showCurrentRecord();
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

function showLast() {
    if (records.length === 0) {
        return;
    }

    currentIndex = records.length - 1;
    showCurrentRecord();
}

function jumpToPosition(event) {
    if (event.key !== "Enter") {
        return;
    }

    const positionInput = document.getElementById("positionInput");
    const position = Number(positionInput.value);

    if (
        !Number.isInteger(position) ||
        position < 1 ||
        position > records.length
    ) {
        positionInput.value  = currentIndex + 1;
        return;
    }

    currentIndex = position - 1;
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
    analyzeCurrentRecord();
}

function clearAnalysisResult() {
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`featureName${i}`).textContent = "-";
        document.getElementById(`featureValue${i}`).textContent = "-";
    }
}

async function analyzeCurrentRecord() {
    if (currentIndex < 0 || currentIndex >= records.length) {
        setStatus("解析するデータがありません。");
        return;
    }

    const functionName = document.getElementById("analysisFunction").value;

    if (!functionName) {
        clearAnalysisResult();
        return;
    }

    const record = records[currentIndex];

    try {
        const result = await window.pywebview.api.analyze_data(
            functionName,
            record.values,
        );

        console.log(result);

        showAnalysisResult(result);

    } catch (error) {
        clearAnalysisResult();
        setStatus(`解析エラー: ${error}`)
    }
}

async function outputAnalysisCsv() {
    if (records.length === 0) {
        setStatus("CSV出力するデータがありません。");
        return;
    }

    const functionName = document.getElementById("analysisFunction").value;

    if (!functionName) {
        setStatus("解析関数を選択してください。");
        return;
    }

    try {
        const result = await window.pywebview.api.output_analysis_csv(
            functionName,
            records,
        )

        setStatus(`特徴量CSVを出力しました。${result.record_count} 件`);
    } catch (error) {
        setStatus(`CSV出力エラー: ${error}`);
    }
}

function showAnalysisResult(result) {
    clearAnalysisResult();

    for (let i = 0; i < result.features.length; i++) {
        const feature = result.features[i];

        document.getElementById(`featureName${i + 1}`).textContent = feature.name;
        document.getElementById(`featureValue${i + 1}`).textContent = feature.value;
    }
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
    const firstButton = document.getElementById("firstButton");
    const previousButton = document.getElementById("previousButton");
    const nextButton = document.getElementById("nextButton");
    const lastButton = document.getElementById("lastButton");

    const positionInput = document.getElementById("positionInput");
    const positionTotal = document.getElementById("positionTotal");

    if (records.length === 0 || currentIndex < 0) {
        positionInput.value = "";
        positionInput.disabled = true;

        positionTotal.textContent = "/ 0 件";

        firstButton.disabled = true;
        previousButton.disabled = true;
        nextButton.disabled = true;
        lastButton.disabled = true;

        return;
    }

    positionInput.disabled = false;

    positionInput.value = currentIndex + 1;
    positionInput.max = records.length;

    positionTotal.textContent = `/ ${records.length} 件`;

    firstButton.disabled = currentIndex === 0;
    previousButton.disabled = currentIndex === 0;

    nextButton.disabled = currentIndex === records.length - 1;
    lastButton.disabled = currentIndex === records.length - 1;
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
