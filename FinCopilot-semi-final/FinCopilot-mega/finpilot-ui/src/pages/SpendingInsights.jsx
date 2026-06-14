import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import MetricCard from '../components/MetricCard';
import { getSpendingSummary } from '../api/client';

export default function SpendingInsights() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  // NEW: State for our simulated transactions
  const [transactions, setTransactions] = useState([]);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    getSpendingSummary()
      .then(res => setData(res.data))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  // NEW: Function to trigger the backend data generation
  const loadDemoTransactions = async () => {
    setSyncing(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/cashflow/transactions');
      const result = await response.json();
      if (result.transactions) {
        setTransactions(result.transactions);
      }
    } catch (error) {
      console.error("Failed to fetch simulated transactions:", error);
    }
    setSyncing(false);
  };

  const fmt = (v) => `₹${Number(v).toLocaleString('en-IN')}`;

  return (
    <div className="layout-content" style={{ paddingTop: 'var(--stack-lg)' }}>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span className="material-symbols-outlined" style={{ color: 'var(--accent-emerald)' }}>analytics</span>
          <h1 className="text-headline-md" style={{ fontWeight: 700 }}>Spending Insights</h1>
        </div>
        <p className="text-body-sm" style={{ color: 'var(--text-muted)', marginBottom: 'var(--stack-lg)' }}>
          Analyze your spending habits and predict next week's budget.
        </p>

        {loading ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
            <span className="material-symbols-outlined animate-pulse" style={{ fontSize: 36, color: 'var(--accent-emerald)' }}>hourglass_empty</span>
            <p className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 12 }}>Loading spending data...</p>
          </div>
        ) : data ? (
          <>
            {/* Metric Cards */}
            <div className="grid-4" style={{ marginBottom: 'var(--stack-lg)' }}>
              <MetricCard label="Total Tracked" value={fmt(data.total_tracked)} icon="receipt_long" color="var(--accent-blue)" />
              <MetricCard label="Days Tracked" value={data.days_tracked} icon="calendar_month" color="var(--text-secondary)" />
              <MetricCard label="Daily Average" value={fmt(data.avg_daily)} icon="trending_flat" color="var(--accent-amber)" />
              <MetricCard label="Next Week Prediction" value={fmt(data.prediction_next_week)} icon="query_stats" color="var(--accent-violet)" />
            </div>

            {/* Insights */}
            <div className="card" style={{ marginBottom: 'var(--stack-md)' }}>
              <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 16 }}>Behavioral Insights</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {data.insights?.map((insight, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="ai-reasoning"
                    style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)' }}
                  >
                    {insight}
                  </motion.div>
                ))}
              </div>
            </div>

            {/* NEW: Simulated Transactions Ledger */}
            <div className="card" style={{ marginBottom: 'var(--stack-md)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div className="text-label-caps" style={{ color: 'var(--text-muted)' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 6, color: 'var(--accent-emerald)' }}>receipt</span>
                  Simulated Transactions Ledger
                </div>
                <button
                  onClick={loadDemoTransactions}
                  disabled={syncing}
                  style={{
                    background: 'var(--bg-container)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: syncing ? 'not-allowed' : 'pointer',
                    opacity: syncing ? 0.7 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseOver={(e) => !syncing && (e.currentTarget.style.borderColor = 'var(--accent-emerald)')}
                  onMouseOut={(e) => !syncing && (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{syncing ? 'sync' : 'download'}</span>
                  {syncing ? 'Generating...' : 'Sync Demo Data'}
                </button>
              </div>

              {transactions.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '10px 12px', fontWeight: 500 }}>Date</th>
                        <th style={{ padding: '10px 12px', fontWeight: 500 }}>Vendor</th>
                        <th style={{ padding: '10px 12px', fontWeight: 500 }}>Category</th>
                        <th style={{ padding: '10px 12px', fontWeight: 500, textAlign: 'right' }}>Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.slice(0, 5).map((txn, idx) => (
                        <motion.tr
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: idx * 0.05 }}
                          key={idx}
                          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
                        >
                          {/* Notice the Capital letters and 'Description' below! */}
                          <td style={{ padding: '12px', color: 'var(--text-muted)' }}>{txn.Date}</td>
                          <td style={{ padding: '12px', color: 'var(--text-primary)' }}>{txn.Description}</td>
                          <td style={{ padding: '12px' }}>
                            <span style={{
                              background: 'var(--bg-container)',
                              border: '1px solid var(--border-subtle)',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '11px',
                              color: 'var(--accent-blue)'
                            }}>
                              {txn.Category}
                            </span>
                          </td>
                          <td style={{ padding: '12px', textAlign: 'right', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {/* Using Math.abs to remove the minus sign for a cleaner UI */}
                            ₹{Math.abs(txn.Amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ textAlign: 'center', marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                    Showing 5 of {transactions.length} generated rows
                  </div>
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '30px',
                  border: '1px dashed var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-muted)',
                  fontSize: '13px'
                }}>
                  No data loaded. Click the sync button to generate synthetic transactions.
                </div>
              )}
            </div>

            {/* Prediction Detail */}
            <div className="card">
              <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 16 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 6, color: 'var(--accent-violet)' }}>smart_toy</span>
                ML Prediction Engine
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--stack-md)' }}>
                <div style={{ padding: 20, background: 'var(--bg-container)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 8, fontSize: 10 }}>Model</div>
                  <div className="text-mono" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Linear Regression</div>
                  <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 4 }}>Trained on weekly spending aggregates</div>
                </div>
                <div style={{ padding: 20, background: 'var(--bg-container)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 8, fontSize: 10 }}>Prediction Confidence</div>
                  <div className="text-mono" style={{ color: 'var(--accent-violet)', fontWeight: 600 }}>~85%</div>
                  <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 4 }}>Based on {data.days_tracked} days of data</div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--text-muted)', opacity: 0.3, display: 'block', marginBottom: 12 }}>analytics</span>
            <p className="text-body-sm" style={{ color: 'var(--text-muted)' }}>
              Start the API server to load spending data.
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}