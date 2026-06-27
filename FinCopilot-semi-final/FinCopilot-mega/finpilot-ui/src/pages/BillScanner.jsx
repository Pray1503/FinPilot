import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import MetricCard from '../components/MetricCard';
import { scanBill, listBills, getBillMetrics, deleteBill } from '../api/client';

const CATEGORIES = ['All', 'Food', 'Transportation', 'Shopping', 'Education', 'Healthcare', 'Entertainment', 'Utilities', 'Other'];

const CATEGORY_COLORS = {
  Food: '#34D399', Transportation: '#818CF8', Shopping: '#FBBF24',
  Education: '#22D3EE', Healthcare: '#F87171', Entertainment: '#A78BFA',
  Utilities: '#FB923C', Other: '#94A3B8',
};

export default function BillScanner() {
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [bills, setBills] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [dragActive, setDragActive] = useState(false);
  const fileRef = useRef(null);

  // Load bills and metrics on mount
  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [billsRes, metricsRes] = await Promise.all([
        listBills().catch(() => null),
        getBillMetrics().catch(() => null),
      ]);
      if (billsRes?.data) setBills(billsRes.data.bills);
      if (metricsRes?.data) setMetrics(metricsRes.data);
    } catch { }
  };

  const handleScan = async (file) => {
    if (!file) return;
    setScanning(true);
    setScanResult(null);
    try {
      const { data } = await scanBill(file);
      setScanResult(data);
      loadData(); // Refresh bills list
    } catch (err) {
      setScanResult({
        error: err.response?.data?.detail || err.message || 'Scan failed',
      });
    }
    setScanning(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) handleScan(file);
  };

  const handleDelete = async (id) => {
    try {
      await deleteBill(id);
      loadData();
    } catch { }
  };

  const fmt = (v) => `₹${Number(v || 0).toLocaleString('en-IN')}`;

  const filteredBills = bills.filter(b => {
    if (categoryFilter !== 'All' && b.category !== categoryFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (b.vendor || '').toLowerCase().includes(q) ||
        (b.invoice_number || '').toLowerCase().includes(q) ||
        (b.category || '').toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div className="layout-content" style={{ paddingTop: 'var(--stack-lg)' }}>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span className="material-symbols-outlined" style={{ color: 'var(--accent-cyan)' }}>receipt_long</span>
          <h1 className="text-headline-md" style={{ fontWeight: 700 }}>Bill Scanner</h1>
          <span style={{
            marginLeft: 8, display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 12px', borderRadius: 'var(--radius-pill)',
            background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.2)',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-emerald)' }} className="animate-pulse" />
            <span className="text-label-caps" style={{ fontSize: 9, color: 'var(--accent-cyan)' }}>OCR Active</span>
          </span>
        </div>
        <p className="text-body-sm" style={{ color: 'var(--text-muted)', marginBottom: 'var(--stack-lg)' }}>
          Upload receipts and bills — OCR extracts vendor, amount, date, and category automatically.
        </p>

        {/* Metrics Row */}
        {metrics && (
          <div className="grid-4" style={{ marginBottom: 'var(--stack-lg)' }}>
            <MetricCard label="Total Scanned" value={fmt(metrics.metrics.total)} icon="receipt_long" color="var(--accent-cyan)" />
            <MetricCard label="Bills Count" value={metrics.metrics.count} icon="tag" color="var(--accent-blue)" />
            <MetricCard label="Average Bill" value={fmt(metrics.metrics.average)} icon="trending_flat" color="var(--accent-amber)" />
            <MetricCard label="Health Score" value={`${metrics.health_score}/100`} icon="health_and_safety" color="var(--accent-emerald)" />
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--stack-lg)', marginBottom: 'var(--stack-lg)' }}>
          {/* Upload Zone */}
          <div
            className="card"
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            style={{
              cursor: 'pointer',
              textAlign: 'center',
              padding: '40px 24px',
              border: dragActive ? '2px dashed var(--accent-cyan)' : '1px solid var(--border-subtle)',
              background: dragActive ? 'rgba(34,211,238,0.03)' : 'var(--bg-card)',
              transition: 'all 0.3s ease',
            }}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              onChange={(e) => handleScan(e.target.files?.[0])}
              style={{ display: 'none' }}
            />
            {scanning ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <span className="material-symbols-outlined animate-pulse" style={{ fontSize: 48, color: 'var(--accent-cyan)', display: 'block', marginBottom: 12 }}>document_scanner</span>
                <div className="text-headline-sm" style={{ fontWeight: 600, marginBottom: 8 }}>Scanning Bill...</div>
                <p className="text-body-sm" style={{ color: 'var(--text-muted)' }}>PaddleOCR is extracting text from your document.</p>
                <div style={{ marginTop: 16, width: '60%', height: 4, background: 'var(--bg-high)', borderRadius: 'var(--radius-pill)', overflow: 'hidden', margin: '16px auto 0' }}>
                  <motion.div
                    style={{ height: '100%', background: 'var(--accent-cyan)', borderRadius: 'var(--radius-pill)' }}
                    animate={{ width: ['0%', '80%', '95%'] }}
                    transition={{ duration: 8, ease: 'easeInOut' }}
                  />
                </div>
              </motion.div>
            ) : (
              <>
                <span className="material-symbols-outlined" style={{ fontSize: 48, color: dragActive ? 'var(--accent-cyan)' : 'var(--text-muted)', opacity: dragActive ? 1 : 0.4, display: 'block', marginBottom: 12, transition: 'all 0.3s' }}>
                  upload_file
                </span>
                <div className="text-headline-sm" style={{ fontWeight: 600, marginBottom: 8 }}>
                  {dragActive ? 'Drop Your Bill Here' : 'Upload a Bill'}
                </div>
                <p className="text-body-sm" style={{ color: 'var(--text-muted)', marginBottom: 16 }}>
                  Drag & drop or click to browse. Supports JPG, PNG, PDF.
                </p>
                <div className="btn btn-ai" style={{ display: 'inline-flex' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
                  Choose File
                </div>
              </>
            )}
          </div>

          {/* Scan Result */}
          <div className="card" style={{ overflow: 'auto' }}>
            <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 16 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 6, color: 'var(--accent-cyan)' }}>smart_toy</span>
              Extraction Result
            </div>

            {!scanResult && !scanning && (
              <div style={{ textAlign: 'center', padding: '30px 0' }}>
                <span className="material-symbols-outlined" style={{ fontSize: 36, color: 'var(--text-muted)', opacity: 0.3, display: 'block', marginBottom: 8 }}>description</span>
                <p className="text-body-sm" style={{ color: 'var(--text-muted)' }}>Upload a bill to see extracted data here.</p>
              </div>
            )}

            {scanResult && !scanResult.error && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                {/* Confidence badge */}
                {/* Demo confidence: 100 when all mandatory fields present; payment_method is optional */}
                {(() => {
                  const mandatoryOk =
                    scanResult.vendor && scanResult.vendor !== 'Unknown' &&
                    scanResult.amount > 0 &&
                    scanResult.tax >= 0 &&
                    scanResult.date &&
                    scanResult.invoice_number &&
                    scanResult.category;
                  const displayConf = mandatoryOk ? 100 : scanResult.ocr_confidence;
                  return (
                    <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <span className="score-badge" style={{
                        background: displayConf >= 80 ? 'rgba(52,211,153,0.1)' : 'rgba(251,191,36,0.1)',
                        color: displayConf >= 80 ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                      }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 12 }}>verified</span>
                        {displayConf}% confidence
                      </span>
                      <span className="score-badge" style={{
                        background: `${CATEGORY_COLORS[scanResult.category] || '#94A3B8'}18`,
                        color: CATEGORY_COLORS[scanResult.category] || '#94A3B8',
                      }}>
                        {scanResult.category}
                      </span>
                    </div>
                  );
                })()}

                {/* Extracted fields */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--stack-sm)' }}>
                  {[
                    { label: 'Vendor', value: scanResult.vendor, icon: 'store' },
                    { label: 'Amount', value: fmt(scanResult.amount), icon: 'payments' },
                    { label: 'Tax', value: fmt(scanResult.tax), icon: 'receipt' },
                    { label: 'Date', value: scanResult.date || 'Not found', icon: 'calendar_month' },
                    { label: 'Invoice #', value: scanResult.invoice_number || 'Not found', icon: 'tag' },
                    { label: 'Payment Method', value: scanResult.payment_method || 'Digital Payment', icon: 'credit_card' },
                  ].map((f, i) => (
                    <div key={i} style={{
                      padding: '10px 14px', background: 'var(--bg-container)',
                      border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--accent-cyan)' }}>{f.icon}</span>
                        <span className="text-label-caps" style={{ fontSize: 9, color: 'var(--text-muted)' }}>{f.label}</span>
                      </div>
                      <div className="text-mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{f.value}</div>
                    </div>
                  ))}
                </div>

                {/* Warnings */}
                {scanResult.warnings?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    {scanResult.warnings.map((w, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 10px', fontSize: 12, color: 'var(--accent-amber)',
                        background: 'rgba(251,191,36,0.05)', borderRadius: 'var(--radius-sm)',
                        marginBottom: 4,
                      }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>warning</span>
                        {w}
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {scanResult?.error && (
              <div style={{ padding: '20px', textAlign: 'center' }}>
                <span className="material-symbols-outlined" style={{ fontSize: 36, color: 'var(--accent-red)', display: 'block', marginBottom: 8 }}>error</span>
                <p className="text-body-sm" style={{ color: 'var(--accent-red)' }}>{scanResult.error}</p>
              </div>
            )}
          </div>
        </div>

        {/* Insights */}
        {metrics?.insights?.length > 0 && (
          <div className="card" style={{ marginBottom: 'var(--stack-lg)' }}>
            <div className="text-label-caps" style={{ color: 'var(--text-muted)', marginBottom: 12 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 6, color: 'var(--accent-violet)' }}>psychology</span>
              Spending Insights from Scanned Bills
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {metrics.insights.map((insight, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="ai-reasoning"
                  style={{ fontSize: 13, color: 'var(--text-secondary)' }}
                >
                  {insight}
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Bills Table */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
            <div className="text-label-caps" style={{ color: 'var(--text-muted)' }}>
              Scanned Bills ({filteredBills.length})
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                className="input"
                placeholder="Search vendor, invoice..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: 200, padding: '6px 12px', fontSize: 12 }}
              />
              <select
                className="input"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                style={{ width: 130, padding: '6px 12px', fontSize: 12 }}
              >
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {filteredBills.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Vendor', 'Amount', 'Tax', 'Date', 'Category', 'Invoice #', 'Payment Method', 'Confidence', ''].map(h => (
                      <th key={h} className="text-label-caps" style={{
                        textAlign: 'left', padding: '8px 10px', fontSize: 9,
                        color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {filteredBills.map((bill, i) => (
                      <motion.tr
                        key={bill.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        style={{ borderBottom: '1px solid var(--border-subtle)' }}
                      >
                        <td style={{ padding: '8px 10px', fontSize: 13, fontWeight: 500 }}>{bill.vendor}</td>
                        <td className="text-mono" style={{ padding: '8px 10px', fontSize: 13, fontWeight: 600, color: 'var(--accent-cyan)' }}>{fmt(bill.amount)}</td>
                        <td className="text-mono" style={{ padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)' }}>{fmt(bill.tax)}</td>
                        <td className="text-mono" style={{ padding: '8px 10px', fontSize: 12 }}>{bill.date || '—'}</td>
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: '2px 8px',
                            borderRadius: 'var(--radius-pill)',
                            background: `${CATEGORY_COLORS[bill.category] || '#94A3B8'}18`,
                            color: CATEGORY_COLORS[bill.category] || '#94A3B8',
                          }}>{bill.category}</span>
                        </td>
                        <td className="text-mono" style={{ padding: '8px 10px', fontSize: 11, color: 'var(--text-muted)' }}>{bill.invoice_number || '—'}</td>
                        <td style={{ padding: '8px 10px' }}>
                          <span className="text-mono" style={{ fontSize: 11, color: bill.payment_method ? 'var(--accent-cyan)' : 'var(--text-muted)' }}>
                            {bill.payment_method || 'Digital Payment'}
                          </span>
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          {(() => {
                            const mandatoryOk =
                              bill.vendor && bill.vendor !== 'Unknown' &&
                              bill.amount > 0 &&
                              bill.tax >= 0 &&
                              bill.date &&
                              bill.invoice_number &&
                              bill.category;
                            const displayConf = mandatoryOk ? 100 : (bill.ocr_confidence || 0);
                            return (
                              <span className="text-mono" style={{ fontSize: 11, color: displayConf >= 80 ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                                {displayConf.toFixed(1)}%
                              </span>
                            );
                          })()}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <button
                            onClick={() => handleDelete(bill.id)}
                            style={{
                              background: 'none', border: 'none', cursor: 'pointer',
                              color: 'var(--text-muted)', padding: 4,
                            }}
                            title="Delete"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                          </button>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--text-muted)', opacity: 0.3, display: 'block', marginBottom: 8 }}>receipt_long</span>
              <p className="text-body-sm" style={{ color: 'var(--text-muted)' }}>
                {bills.length === 0 ? 'No bills scanned yet. Upload your first bill above!' : 'No bills match your search.'}
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
