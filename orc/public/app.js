const fields = {
  question: document.querySelector("#question"),
  income: document.querySelector("#income"),
  expenses: document.querySelector("#expenses"),
  savings: document.querySelector("#savings"),
  debt: document.querySelector("#debt"),
  loan: document.querySelector("#loan"),
  emi: document.querySelector("#emi"),
  emergency: document.querySelector("#emergency"),
  course: document.querySelector("#course"),
  uplift: document.querySelector("#uplift"),
  outflows: document.querySelector("#outflows"),
  goals: document.querySelector("#goals")
};

const runButton = document.querySelector("#run");

function number(id) {
  return Number(fields[id].value || 0);
}

function parseGoals(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, target_date, required_amount] = line.split(",").map((part) => part.trim());
      return {
        name,
        target_date,
        required_amount: Number(required_amount || 0)
      };
    });
}

function requestPayload() {
  return {
    user_question: fields.question.value,
    user_profile: {
      income_monthly: number("income"),
      monthly_expenses: number("expenses"),
      savings: number("savings"),
      existing_debt_monthly_EMI: number("debt"),
      requested_loan_amount: number("loan"),
      proposed_EMI: number("emi"),
      emergency_fund_amount: number("emergency"),
      course_length_months: number("course"),
      expected_skill_earning_uplift_pct: number("uplift"),
      other_known_outflows: number("outflows"),
      goals: parseGoals(fields.goals.value)
    }
  };
}

function verdictClass(verdict = "") {
  return verdict.toLowerCase();
}

function setThinking(isThinking) {
  document.querySelectorAll(".card, .coordinator").forEach((card) => {
    card.classList.toggle("thinking", isThinking);
  });
  runButton.disabled = isThinking;
}

function renderSpecialist(id, verdict, numbers, analysis) {
  const card = document.querySelector(id);
  const verdictNode = card.querySelector(".verdict");
  verdictNode.textContent = verdict;
  verdictNode.className = `verdict ${verdictClass(verdict)}`;
  card.querySelector(".numbers").textContent = numbers;
  card.querySelector(".analysis").textContent = analysis;
}

function render(data) {
  renderSpecialist(
    "#budget-card",
    data.budgeter.verdict,
    `DTI ${data.budgeter.key_numbers.debt_to_income_pct}% | EMI ${data.budgeter.key_numbers.proposed_emi_pct}% | savings ${data.budgeter.key_numbers.savings_months_coverage} mo`,
    data.budgeter.analysis
  );

  renderSpecialist(
    "#planner-card",
    data.planner.verdict,
    `ROI estimate ${data.planner.roi_months_estimate} months`,
    data.planner.analysis
  );

  renderSpecialist(
    "#realist-card",
    data.realist.verdict,
    `Emergency fund ${data.realist.emergency_fund_months} mo | ${data.realist.key_risks.join(", ") || "no major risks flagged"}`,
    data.realist.analysis
  );

  const coordinator = data.coordinator;
  const coordinatorCard = document.querySelector("#coordinator-card");
  const verdictNode = coordinatorCard.querySelector(".verdict");
  verdictNode.textContent = coordinator.combined_verdict;
  verdictNode.className = `verdict ${verdictClass(coordinator.combined_verdict)}`;
  coordinatorCard.querySelector(".recommendation").textContent = coordinator.coordinator_recommendation;
  document.querySelector("#agrees").textContent = coordinator.agrees;
  document.querySelector("#tradeoff").textContent = coordinator.tradeoff;
  document.querySelector("#steps").innerHTML = coordinator.next_steps
    .map((step) => `<li><strong>${step.timeframe_days} days:</strong> ${step.action}</li>`)
    .join("");
}

async function runBoardroom() {
  setThinking(true);
  try {
    const response = await fetch("/api/boardroom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload())
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    render(await response.json());
  } catch (error) {
    alert(error.message);
  } finally {
    setThinking(false);
  }
}

runButton.addEventListener("click", runBoardroom);
runBoardroom();
