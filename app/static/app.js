async function run() {
    const question = document.getElementById("question").value;
    const btn = document.getElementById("analyzeBtn");
    const spinner = document.getElementById("spinner");

    // show spinner and disable button
    spinner.classList.remove("hidden");
    spinner.setAttribute("aria-hidden", "false");
    btn.disabled = true;

    try {
        const res = await fetch("http://localhost:8000/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ question })
        });

        const data = await res.json();

        document.getElementById("sql").innerText =
            "SQL:\n" + data.sql;

        document.getElementById("results").innerText =
            "Results:\n" + JSON.stringify(data.results, null, 2);

        document.getElementById("insight").innerText =
            "Insight:\n" + data.insight;

        document.getElementById("rule").innerText =
            "Rule:\n" + data.rule;

        document.getElementById("evaluation").innerText =
            "Evaluation:\n" + JSON.stringify(data.evaluation, null, 2);
    } catch (err) {
        document.getElementById("results").innerText = "Results:\nError: " + err.message;
    } finally {
        // hide spinner and re-enable button
        spinner.classList.add("hidden");
        spinner.setAttribute("aria-hidden", "true");
        btn.disabled = false;
    }
}

window.run = run;