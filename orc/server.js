import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "public");
const port = Number(process.env.PORT || 3000);

function round(value, digits = 2) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : 0;
}

function asNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function parseLoanAmount(question = "") {
  const match = question.replace(/,/g, "").match(/(?:\u20b9|rs\.?|inr)?\s*(\d{4,})/i);
  return match ? Number(match[1]) : 0;
}

function estimateProposedEmi(profile, requestedLoanAmount) {
  if (profile.proposed_EMI !== undefined && profile.proposed_EMI !== null) {
    return asNumber(profile.proposed_EMI);
  }

  const amount = requestedLoanAmount || asNumber(profile.requested_loan_amount);
  return amount > 0 ? round(amount * 0.07, 0) : 0;
}

function buildProfile(input = {}) {
  const profile = input.user_profile || {};
  const requestedLoanAmount = asNumber(profile.requested_loan_amount) || parseLoanAmount(input.user_question);
  const proposedEmi = estimateProposedEmi(profile, requestedLoanAmount);
  const monthlyExpenses = asNumber(profile.monthly_expenses);
  const otherOutflows = asNumber(profile.other_known_outflows);
  const emergencyFundAmount = asNumber(profile.emergency_fund_amount, asNumber(profile.savings));

  return {
    original_question: input.user_question || "",
    income_monthly: asNumber(profile.income_monthly),
    monthly_expenses: monthlyExpenses,
    savings: asNumber(profile.savings),
    existing_debt_monthly_EMI: asNumber(profile.existing_debt_monthly_EMI),
    requested_loan_amount: requestedLoanAmount,
    proposed_EMI: proposedEmi,
    proposed_EMI_was_estimated: profile.proposed_EMI === undefined || profile.proposed_EMI === null,
    other_known_outflows: otherOutflows,
    emergency_fund_amount: emergencyFundAmount,
    goals: Array.isArray(profile.goals) ? profile.goals : [],
    expected_skill_earning_uplift_pct: profile.expected_skill_earning_uplift_pct,
    course_length_months: asNumber(profile.course_length_months),
    user_profile: profile,
    upcoming_fixed_obligations: Array.isArray(profile.upcoming_fixed_obligations) ? profile.upcoming_fixed_obligations : [],
    seasonality_flags: Array.isArray(profile.seasonality_flags) ? profile.seasonality_flags : [],
    credit_history: profile.credit_history || "unknown",
    expense_volatility_metric: profile.expense_volatility_metric || "unknown"
  };
}

function profileSummary(profile) {
  const emergencyMonths = profile.monthly_expenses > 0
    ? round(profile.emergency_fund_amount / profile.monthly_expenses, 2)
    : 0;

  return {
    income: profile.income_monthly,
    monthly_expenses: profile.monthly_expenses,
    savings: profile.savings,
    emergency_fund_months: emergencyMonths,
    existing_debt_EMI: profile.existing_debt_monthly_EMI,
    top_3_goals: profile.goals.slice(0, 3).map((goal) => ({
      name: goal.name,
      target_date: goal.target_date
    }))
  };
}

function budgetAnalyst(profile) {
  const totalDebt = profile.existing_debt_monthly_EMI + profile.proposed_EMI;
  const obligations = profile.monthly_expenses + totalDebt + profile.other_known_outflows;
  const debtToIncomePct = profile.income_monthly > 0 ? (totalDebt / profile.income_monthly) * 100 : 0;
  const proposedEmiPct = profile.income_monthly > 0 ? (profile.proposed_EMI / profile.income_monthly) * 100 : 0;
  const savingsMonthsCoverage = profile.monthly_expenses > 0 ? profile.savings / profile.monthly_expenses : 0;
  const needsPct = profile.income_monthly > 0 ? (profile.monthly_expenses / profile.income_monthly) * 100 : 0;
  const savingsPct = profile.income_monthly > 0 ? (profile.savings / profile.income_monthly) * 100 : 0;
  const wantsPct = Math.max(0, 100 - needsPct - savingsPct - debtToIncomePct);
  const cashFlowShortfall = profile.income_monthly - obligations < 0;

  let verdict = "Safe";
  if (cashFlowShortfall || debtToIncomePct > 40 || savingsMonthsCoverage < 1) verdict = "Risky";
  else if (debtToIncomePct > 25 || proposedEmiPct > 15 || savingsMonthsCoverage < 2) verdict = "Caution";

  const splitStatus = `needs ${round(needsPct, 1)}%, wants ${round(wantsPct, 1)}%, savings ${round(savingsPct, 1)}%: ${needsPct <= 55 && savingsPct >= 15 ? "approximate" : "violates"} 50/30/20`;
  const emiNote = profile.proposed_EMI_was_estimated ? `Estimated EMI is ${profile.proposed_EMI}. ` : "";
  const analysis = `${emiNote}Debt-to-income is ${round(debtToIncomePct, 1)}% and proposed EMI is ${round(proposedEmiPct, 1)}% of income. ${splitStatus}; monthly cash flow ${cashFlowShortfall ? "falls short" : "stays non-negative"} after obligations.`;

  return {
    verdict,
    key_numbers: {
      debt_to_income_pct: round(debtToIncomePct, 2),
      proposed_emi_pct: round(proposedEmiPct, 2),
      savings_months_coverage: round(savingsMonthsCoverage, 2)
    },
    analysis
  };
}

function longTermPlanner(profile) {
  const upliftPct = asNumber(profile.expected_skill_earning_uplift_pct, 25);
  const monthlyIncomeLift = profile.income_monthly * (upliftPct / 100);
  const roiMonths = monthlyIncomeLift > 0
    ? Math.ceil(profile.requested_loan_amount / monthlyIncomeLift) + profile.course_length_months + 2
    : 0;

  const goalImpacts = profile.goals.slice(0, 5).map((goal) => {
    const text = `${goal.name || ""} ${goal.notes || ""}`.toLowerCase();
    const helps = /placement|job|career|skill|course|prep|earning|income/.test(text);
    const delays = asNumber(goal.required_amount) > 0 && profile.proposed_EMI > 0 && !helps;

    return {
      goal_name: goal.name || "Unnamed goal",
      impact: helps ? "helps" : delays ? "delays" : "neutral",
      notes: helps
        ? "The course can support this goal if the income uplift arrives on schedule."
        : delays
          ? "Loan EMI reduces monthly room to fund this goal."
          : "No direct effect from the course is clear."
    };
  });

  const hasHelpingGoal = goalImpacts.some((goal) => goal.impact === "helps");
  const verdict = hasHelpingGoal && roiMonths > 0 && roiMonths <= 12 && profile.emergency_fund_amount >= profile.monthly_expenses * 2
    ? "High_impact"
    : hasHelpingGoal || (roiMonths > 0 && roiMonths <= 24)
      ? "Moderate"
      : "Low_impact";
  const firstGoal = goalImpacts[0]?.goal_name || "the stated goals";
  const analysis = `Using a ${upliftPct}% income-uplift assumption, best-case breakeven is about ${roiMonths || "unknown"} months after the course starts paying off. This can help ${firstGoal}, but borrowing now trades away savings flexibility and alternative goal funding during the EMI period.`;

  return {
    verdict,
    roi_months_estimate: roiMonths,
    goal_impacts: goalImpacts,
    analysis
  };
}

function riskAssessor(profile) {
  const emergencyFundMonths = profile.monthly_expenses > 0
    ? profile.emergency_fund_amount / profile.monthly_expenses
    : 0;
  const targetGap = Math.max(0, (profile.monthly_expenses * 2) - profile.emergency_fund_amount);
  const emiDrainMonths = profile.proposed_EMI > 0
    ? Math.ceil(profile.emergency_fund_amount / profile.proposed_EMI)
    : 0;

  const keyRisks = [];
  if (emergencyFundMonths < 2) keyRisks.push("no 2-month buffer");
  if (profile.income_monthly - profile.monthly_expenses - profile.proposed_EMI - profile.existing_debt_monthly_EMI - profile.other_known_outflows < 0) {
    keyRisks.push("cash flow can turn negative after EMI");
  }
  if (profile.credit_history === "unknown") keyRisks.push("credit history is unknown");
  if (profile.expense_volatility_metric === "high") keyRisks.push("expenses are volatile");
  if (profile.seasonality_flags.length > 0) keyRisks.push("seasonal expense spikes are expected");

  const verdict = emergencyFundMonths < 1 || keyRisks.includes("cash flow can turn negative after EMI")
    ? "Too_risky"
    : emergencyFundMonths < 2 || keyRisks.length >= 2
      ? "Proceed_with_caution"
      : "Manageable_risk";
  const analysis = `Emergency fund covers ${round(emergencyFundMonths, 2)} months against a 2-month target, leaving a buffer gap of Rs ${round(targetGap, 0)}. Worst case: an income interruption could force EMI payments from savings for about ${emiDrainMonths} month(s), quickly consuming the current buffer.`;

  return {
    verdict,
    key_risks: keyRisks.slice(0, 3),
    emergency_fund_months: round(emergencyFundMonths, 2),
    analysis
  };
}

function coordinator(profile, budgeter, planner, realist, summary) {
  const riskyBudget = budgeter.verdict === "Risky";
  const riskyRealist = realist.verdict === "Too_risky";
  const positiveRoi = planner.verdict === "High_impact" || planner.verdict === "Moderate";
  const emergencyTarget = profile.monthly_expenses * 2;
  const emergencyGap = Math.max(0, emergencyTarget - profile.emergency_fund_amount);
  const weeklySave = Math.max(250, Math.ceil(emergencyGap / 8));

  const combined_verdict = riskyBudget || riskyRealist
    ? "Delay_and_prepare"
    : positiveRoi
      ? "Go_now"
      : "Decline";
  const coordinator_recommendation = combined_verdict === "Go_now"
    ? "Recommended: Take the loan only if the EMI stays within the stated amount and you keep at least two months of expenses untouched."
    : combined_verdict === "Delay_and_prepare"
      ? "Recommended: Build 2 months of emergency savings first, then take the loan; consider a smaller loan if urgent."
      : "Recommended: Do not take this loan now because the financial strain outweighs the expected goal impact.";

  return {
    combined_verdict,
    agrees: "All specialists agree the decision depends on EMI affordability and keeping a cash buffer.",
    tradeoff: positiveRoi
      ? "The tradeoff is career upside now versus thin emergency savings during repayment."
      : "The tradeoff is immediate access to the course versus delaying other goals without clear ROI.",
    coordinator_recommendation,
    next_steps: [
      {
        action: `Save Rs ${weeklySave} per week toward the 2-month emergency buffer.`,
        timeframe_days: 30
      },
      {
        action: "Apply to at least 3 scholarships, discounts, or no-cost EMI options.",
        timeframe_days: 60
      },
      {
        action: `Re-evaluate with EMI <= Rs ${profile.proposed_EMI || 0}, savings >= Rs ${emergencyTarget}, and updated income prospects.`,
        timeframe_days: 90
      }
    ],
    profile_summary: summary
  };
}

async function parseJsonBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function boardroom(input) {
  const profile = buildProfile(input);
  const summary = profileSummary(profile);
  const budgeter = budgetAnalyst(profile);
  const planner = longTermPlanner(profile);
  const realist = riskAssessor(profile);
  const coordinatorJson = coordinator(profile, budgeter, planner, realist, summary);

  return {
    budgeter,
    planner,
    realist,
    coordinator: coordinatorJson
  };
}

function contentType(filePath) {
  if (filePath.endsWith(".css")) return "text/css";
  if (filePath.endsWith(".js")) return "text/javascript";
  if (filePath.endsWith(".json")) return "application/json";
  return "text/html";
}

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${request.headers.host}`);

    if (request.method === "POST" && url.pathname === "/api/boardroom") {
      const input = await parseJsonBody(request);
      const result = boardroom(input);
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify(result));
      return;
    }

    const requestedPath = url.pathname === "/" ? "/index.html" : url.pathname;
    const safePath = path.normalize(requestedPath).replace(/^(\.\.[/\\])+/, "");
    const filePath = path.join(publicDir, safePath);
    const file = await readFile(filePath);
    response.writeHead(200, { "Content-Type": contentType(filePath) });
    response.end(file);
  } catch (error) {
    const status = error.code === "ENOENT" ? 404 : 500;
    response.writeHead(status, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ error: status === 404 ? "Not found" : error.message }));
  }
});

server.listen(port, () => {
  console.log(`Financial boardroom running at http://localhost:${port}`);
});
