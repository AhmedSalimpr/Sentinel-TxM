import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  Users, 
  TrendingUp, 
  CheckCircle2, 
  RefreshCcw, 
  UserCheck, 
  DollarSign, 
  Clock, 
  Search, 
  Filter, 
  ShieldCheck,
  Activity,
  Globe2,
  Database,
  ArrowRight,
  TrendingDown,
  Network,
  Share2,
  ChevronRight,
  Sparkles
} from 'lucide-react';
import { 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid
} from 'recharts';
import NetworkGraph from './components/NetworkGraph';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 bg-red-500/10 border border-red-500 text-red-400 text-xs font-mono whitespace-pre-wrap overflow-auto h-full w-full">
          {this.state.error.toString()}
          {'\n\n'}
          {this.state.error.stack}
        </div>
      );
    }
    return this.props.children;
  }
}

const API_BASE = `${window.location.origin}/api`;

export default function App() {
  const [alerts, setAlerts] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [selectedAlertId, setSelectedAlertId] = useState(null);
  const [selectedAlertDetail, setSelectedAlertDetail] = useState(null);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [selectedUserDetail, setSelectedUserDetail] = useState(null);
  
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRule, setFilterRule] = useState('mule_cycle');
  const [sortField, setSortField] = useState('risk_weight');
  const [sortOrder, setSortOrder] = useState('desc');
  const [allAlerts, setAllAlerts] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingUser, setLoadingUser] = useState(false);
  
  const [isStreaming, setIsStreaming] = useState(true); // Auto-start by default

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedAlertId(null);
    setSelectedAlertDetail(null);
    setSelectedUserDetail(null);
  }, [filterRule]);

  // Fetch alerts and metrics on mount or when sort changes
  useEffect(() => {
    fetchAlerts();
    fetchMetrics();
  }, [sortField, sortOrder]);

  // Fetch detail when selected alert changes
  useEffect(() => {
    if (selectedAlertId) {
      fetchAlertDetail(selectedAlertId);
    } else {
      setSelectedAlertDetail(null);
    }
  }, [selectedAlertId]);

  // Fetch user profile detail when selected user changes
  useEffect(() => {
    if (selectedUserId) {
      fetchUserProfile(selectedUserId);
    } else {
      setSelectedUserDetail(null);
    }
  }, [selectedUserId]);

  // We will handle auto-selection further down, after filteredAlerts is defined.

  const fetchAlerts = async () => {
    setLoadingAlerts(true);
    try {
      let url = `${API_BASE}/alerts?sort_by=${sortField}&order=${sortOrder}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAllAlerts(data);
        setAlerts([]); // Start empty for streaming
      }
    } catch (err) {
      console.error('Error fetching alerts:', err);
    } finally {
      setLoadingAlerts(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error('Error fetching metrics:', err);
    }
  };

  const fetchAlertDetail = async (id) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`${API_BASE}/alerts/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedAlertDetail(data);
        if (data.alert && data.alert.user_id) {
          setSelectedUserId(data.alert.user_id);
        }
      }
    } catch (err) {
      console.error('Error fetching alert detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const fetchUserProfile = async (userId) => {
    setLoadingUser(true);
    try {
      const res = await fetch(`${API_BASE}/users/${userId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedUserDetail(data);
      }
    } catch (err) {
      console.error('Error fetching user profile:', err);
    } finally {
      setLoadingUser(false);
    }
  };

  const handleRefresh = () => {
    fetchAlerts();
    fetchMetrics();
    if (selectedAlertId) {
      fetchAlertDetail(selectedAlertId);
    }
  };

  useEffect(() => {
    let interval;
    if (isStreaming) {
      interval = setInterval(() => {
        setAlerts(prev => {
          if (allAlerts.length === 0) return prev; // Wait until data is loaded
          const nextIndex = prev.length;
          if (nextIndex >= allAlerts.length) {
            setIsStreaming(false);
            return prev;
          }
          return [allAlerts[nextIndex], ...prev];
        });
      }, 100); // Fast stream (10 transactions per second)
    }
    return () => clearInterval(interval);
  }, [isStreaming, allAlerts]);

  const handleToggleStream = () => {
    if (alerts.length === allAlerts.length) {
      // If finished, reset and start over
      setAlerts([]);
    }
    setIsStreaming(!isStreaming);
  };

  const formatRuleName = (name) => {
    switch (name) {
      case 'structuring': return 'Structuring';
      case 'mule_hub': return 'Mule Hub';
      case 'mule_cycle': return 'Mule Cycle';
      case 'mule_sink': return 'Mule Sink';
      case 'mule_spoke': return 'Mule Spoke';
      case 'mule_cycle_relay': return 'Cycle Relay';
      case 'mule_cycle_spoke': return 'Cycle Spoke';
      case 'roundtrip': return 'Carousel Roundtrip';
      case 'chain': return 'Layered Chain';
      default: return name;
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    const matchesRule = filterRule === '' || alert.rule_name === filterRule;
    const matchesSearch = alert.alert_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      alert.user_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (alert.details && alert.details.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesRule && matchesSearch;
  });

  // Auto-select the first filtered alert if none is selected
  const firstFilteredAlertId = filteredAlerts.length > 0 ? filteredAlerts[0].alert_id : null;
  useEffect(() => {
    if (firstFilteredAlertId && !selectedAlertId) {
      setSelectedAlertId(firstFilteredAlertId);
    }
  }, [firstFilteredAlertId, selectedAlertId]);

  // Calculate total volume laundered via Money Mule networks
  const totalMuleVolume = alerts
    .filter(a => a.rule_name === 'mule_hub' || a.rule_name === 'mule_cycle' || a.rule_name === 'roundtrip' || a.rule_name === 'chain')
    .reduce((sum, a) => sum + (Number(a.total_amount) || 0), 0);

  return (
    <div className="min-h-screen bg-background text-white flex flex-col font-sans antialiased">
      {/* Crisp Light Mode Header */}
      <header className="sticky top-0 z-40 bg-surface border-b border-border shadow-xs px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl overflow-hidden border border-primary/20 shadow-2xs shadow-primary/20 flex-shrink-0">
            <img src="/logo.jpg" alt="Sentinel-TxM Logo" className="w-full h-full object-cover" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white">Sentinel-TxM</h1>
              <span className="text-[10px] font-bold px-2 py-0.5 bg-primary/10 border border-primary/30 text-primary rounded-md tracking-wider uppercase">
                Enterprise
              </span>
            </div>
            <p className="text-[11px] text-muted font-medium">Transaction Monitoring & Graph Intelligence Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Stream Data Button */}
          <button
            onClick={handleToggleStream}
            title="Start simulating real-time transaction monitoring stream"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold border shadow-2xs transition-all ${
              isStreaming
                ? 'bg-danger/10 border-danger/30 text-danger hover:bg-danger/20'
                : 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
            }`}
          >
            <Activity className={`w-3.5 h-3.5 ${isStreaming ? 'animate-pulse text-danger' : 'text-primary'}`} />
            {isStreaming ? 'Stop Stream' : 'Start Stream'}
          </button>
          <button 
            onClick={handleRefresh}
            title="Sync dataset from AWS backend"
            className="flex items-center gap-2 bg-surface hover:bg-background border border-border shadow-2xs px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-300 hover:text-white transition-colors"
          >
            <RefreshCcw className="w-3.5 h-3.5 text-muted" />
            Reset
          </button>
          <div className="h-4 w-[1px] bg-border"></div>
          <div className="flex items-center gap-2 bg-success/10 border border-success/30 px-3 py-1 rounded-lg">
            <span className="w-2 h-2 bg-success/100 rounded-full animate-pulse"></span>
            <span className="text-[11px] font-bold text-success tracking-wide">API LIVE</span>
          </div>
        </div>
      </header>

      {/* Metric Cards Grid */}
      <section className="px-8 pt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Precision */}
        <div className="surface-card surface-card-hover rounded-xl p-5 flex flex-col justify-between h-[115px]">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted font-bold uppercase tracking-wider">Detection Precision</span>
            <div className="p-1.5 bg-primary/10 rounded-lg text-primary">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-2xl font-extrabold tracking-tight text-white">
              {metrics ? `${(metrics.overall.precision * 100).toFixed(1)}%` : '...'}
            </h3>
            <p className="text-[10.5px] text-muted font-medium mt-0.5">True positive anomaly rate</p>
          </div>
        </div>

        {/* Card 2: Recall */}
        <div className="surface-card surface-card-hover rounded-xl p-5 flex flex-col justify-between h-[115px]">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted font-bold uppercase tracking-wider">Model Recall</span>
            <div className="p-1.5 bg-success/10 rounded-lg text-success">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-2xl font-extrabold tracking-tight text-white">
              {metrics ? `${(metrics.overall.recall * 100).toFixed(1)}%` : '...'}
            </h3>
            <p className="text-[10.5px] text-muted font-medium mt-0.5">Flagged suspicious ratio</p>
          </div>
        </div>

        {/* Card 3: Mule Volume */}
        <div className="surface-card surface-card-hover rounded-xl p-5 flex flex-col justify-between h-[115px] border-danger/30 bg-danger/10">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-danger font-bold tracking-wider uppercase">High-Risk Volume Pending Investigation</span>
            <div className="p-1.5 bg-danger/20 rounded-lg text-danger">
              <Share2 className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-2xl font-extrabold tracking-tight text-danger font-mono">
              ${totalMuleVolume.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </h3>
            <p className="text-[10.5px] text-muted font-medium mt-0.5">Identified in network subgraphs</p>
          </div>
        </div>

        {/* Card 4: Compliance Queue */}
        <div className="surface-card surface-card-hover rounded-xl p-5 flex flex-col justify-between h-[115px]">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted font-bold uppercase tracking-wider">Pending Queue</span>
            <div className="p-1.5 bg-warning/10 rounded-lg text-warning">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-2xl font-extrabold tracking-tight text-white font-mono">
              {metrics ? metrics.summary.total_alerts : '...'}
            </h3>
            <p className="text-[10.5px] text-muted font-medium mt-0.5">Active alerts requiring audit</p>
          </div>
        </div>

        {/* Card 5: FPR */}
        <div className="surface-card surface-card-hover rounded-xl p-5 flex flex-col justify-between h-[115px]">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-muted font-bold uppercase tracking-wider">False Positive Rate</span>
            <div className="p-1.5 bg-primary/10 rounded-lg text-primary">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div>
            <h3 className="text-2xl font-extrabold tracking-tight text-white font-mono">
              {metrics ? `${(metrics.overall.false_positive_rate * 100).toFixed(3)}%` : '...'}
            </h3>
            <p className="text-[10.5px] text-muted font-medium mt-0.5">Background normal noise</p>
          </div>
        </div>
      </section>

      {/* Main Workspace split into Queue (left) and Detail Panel (right) */}
      <main className="flex-1 px-8 py-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Section - Alerts View */}
        <section className="lg:col-span-5 flex flex-col" style={{ height: 'calc(100vh - 300px)', minHeight: '520px' }}>
          
          <div className="surface-card rounded-xl flex-1 flex flex-col overflow-hidden shadow-sm border border-border">
            {/* Search & Filter Header */}
            <div className="p-4 border-b border-border bg-surface flex flex-col gap-3">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted" />
                <input
                  type="text"
                  placeholder="Search by ID or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-surface border border-border-bright rounded-lg pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-muted focus:ring-1 focus:ring-slate-200 text-white placeholder-slate-400"
                />
              </div>

              <div className="flex items-center justify-between mb-2 mt-3">
                <div className="flex items-center gap-2">
                  <Filter className="w-4 h-4 text-gray-400" />
                  <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">Categories</span>
                </div>
                <span className="text-[10px] text-muted">{filteredAlerts.length} alerts</span>
              </div>
            
              <div className="flex flex-wrap gap-2 max-h-[180px] overflow-y-auto custom-scrollbar">
                
                {[
                  { id: '', name: 'All', icon: Database },
                  { id: 'mule_hub', name: 'Mule Hub', icon: ShieldCheck },
                  { id: 'mule_cycle', name: 'Mule Cycle', icon: Activity },
                  { id: 'roundtrip', name: 'Carousel', icon: Share2 },
                  { id: 'chain', name: 'Chain', icon: Network },
                  { id: 'structuring', name: 'Structuring', icon: TrendingUp }
                ].map((rule) => {
                  const Icon = rule.icon;
                  const isActive = filterRule === rule.id;
                  
                  return (
                    <button
                      key={rule.id}
                      onClick={() => setFilterRule(rule.id)}
                      className={`flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md border transition-all whitespace-nowrap cursor-pointer ${
                        isActive 
                          ? 'bg-primary border-slate-800 text-white' 
                          : 'bg-surface border-border-bright text-gray-300 hover:bg-background'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{rule.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto bg-surface">
              {loadingAlerts ? (
                <div className="flex items-center justify-center h-full text-muted text-xs gap-2 font-medium p-8">
                  <RefreshCcw className="w-3.5 h-3.5 animate-spin text-primary" />
                  Refreshing queue...
                </div>
              ) : filteredAlerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted p-8 text-center">
                  <AlertTriangle className="w-12 h-12 mb-3 text-muted/50 stroke-[1]" />
                  <p className="text-sm text-gray-400 font-semibold mb-1">No alerts found</p>
                  <p className="text-xs text-muted">Try adjusting your filters to see more results</p>
                </div>
              ) : (
                <table className="w-full text-left border-collapse">
                  <thead className="bg-background/80 sticky top-0 z-10">
                    <tr className="border-b border-border">
                      <th className="px-4 py-3 text-[9px] font-semibold text-muted uppercase tracking-wider">#</th>
                      <th className="px-4 py-3 text-[9px] font-semibold text-muted uppercase tracking-wider">Type</th>
                      <th className="px-4 py-3 text-[9px] font-semibold text-muted uppercase tracking-wider">Account</th>
                      <th className="px-4 py-3 text-[9px] font-semibold text-muted uppercase tracking-wider text-right">Amount</th>
                      <th className="px-4 py-3 text-[9px] font-semibold text-muted uppercase tracking-wider">Risk</th>
                    </tr>
                  </thead>
                  <tbody className="bg-surface divide-y divide-slate-200">
                    {filteredAlerts.map((alert, idx) => {
                      const isSelected = selectedAlertId === alert.alert_id;
                      const risk = alert.risk_weight;

                      return (
                        <tr 
                          key={alert.alert_id}
                          onClick={() => setSelectedAlertId(alert.alert_id)}
                          className={`cursor-pointer transition-all ${
                            isSelected ? 'bg-primary/10' : 'hover:bg-background'
                          }`}
                        >
                          <td className="px-4 py-3 text-center">
                            <span className="text-xs font-mono text-muted">{idx + 1}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center text-xs font-medium px-2 py-1 rounded border ${
                              alert.rule_name === 'mule_hub' ? 'bg-danger/10 text-danger border-danger/30' :
                              alert.rule_name === 'mule_cycle' ? 'bg-warning/10 text-warning border-warning/30' :
                              alert.rule_name === 'roundtrip' ? 'bg-primary/10 text-primary border-primary/30' :
                              alert.rule_name === 'chain' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                              'bg-blue-50 text-blue-700 border-blue-200'
                            }`}>
                              {formatRuleName(alert.rule_name)}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <UserCheck className="w-3.5 h-3.5 text-muted flex-shrink-0" />
                              <span className="text-sm font-mono text-gray-300 truncate" title={alert.user_id}>{alert.user_id.substring(0, 8)}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <span className="text-sm font-mono font-semibold text-white">
                              ${Number(alert.total_amount).toLocaleString(undefined, { minimumFractionDigits: 0 })}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-border rounded-full h-1.5 min-w-[70px] overflow-hidden">
                                <div 
                                  className={`h-full rounded-full ${
                                    risk > 0.75 ? 'bg-danger' : risk > 0.5 ? 'bg-warning' : 'bg-success'
                                  }`}
                                  style={{ width: `${risk * 100}%` }}
                                />
                              </div>
                              <span className={`text-xs font-semibold w-12 text-right ${
                                risk > 0.75 ? 'text-danger' : risk > 0.5 ? 'text-warning' : 'text-success'
                              }`}>
                                {Math.round(risk * 100)}%
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

        </section>

        {/* Right Detail & Graph Section */}
        <section className="lg:col-span-7 flex flex-col overflow-y-auto" style={{ height: 'calc(100vh - 300px)', minHeight: '520px' }}>
          {loadingDetail ? (
            <div className="surface-card rounded-xl flex-1 flex items-center justify-center text-muted text-xs gap-2 font-medium">
              <RefreshCcw className="w-3.5 h-3.5 animate-spin text-primary" />
              Loading case telemetry...
            </div>
          ) : !selectedAlertDetail ? (
            <div className="surface-card rounded-xl flex-1 flex flex-col items-center justify-center text-muted p-8 text-center">
              <Database className="w-10 h-10 mb-3 text-muted/50 stroke-[1.5]" />
              <h3 className="text-gray-300 font-bold text-xs mb-1">No Alert Selected</h3>
              <p className="text-[11px] text-muted max-w-xs">Select a flagged incident from the queue to load force-directed graph analytics.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* Alert Header Summary Panel */}
              <div className="surface-card rounded-xl p-5 text-left shadow-sm bg-surface">
                <div className="flex items-start justify-between border-b border-border pb-4 mb-4">
                  <div>
                    <div className="text-[10.5px] font-mono text-muted font-bold uppercase tracking-wider">
                      INCIDENT CASE ID: {selectedAlertDetail.alert.alert_id}
                    </div>
                    <h2 className="text-base font-bold text-white mt-1">
                      {formatRuleName(selectedAlertDetail.alert.rule_name)} Anomaly Detected
                    </h2>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-muted block uppercase font-bold tracking-wider">Risk Priority</span>
                    <span className={`text-base font-extrabold block mt-0.5 ${
                      selectedAlertDetail.alert.risk_weight > 0.75 ? 'text-danger' : 'text-warning'
                    }`}>
                      {selectedAlertDetail.alert.risk_weight > 0.75 ? 'CRITICAL HIGH' : 'MODERATE'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Network Graph Visualizer (excludes structuring alerts) */}
              {selectedAlertDetail.alert.rule_name !== 'structuring' && (
                <div className="surface-card rounded-xl p-4 text-left h-[500px] w-full relative flex flex-col shadow-sm bg-surface">
                  <ErrorBoundary>
                    <NetworkGraph 
                      subgraph={selectedAlertDetail.subgraph} 
                      onSelectUser={setSelectedUserId}
                      selectedUserId={selectedUserId}
                    />
                  </ErrorBoundary>
                </div>
              )}

              {/* Structuring Time Series View */}
              {selectedAlertDetail.alert.rule_name === 'structuring' && (
                <div className="surface-card rounded-xl p-5 text-left shadow-sm bg-surface">
                  <div className="mb-4">
                    <span className="text-xs font-bold text-gray-300">Structuring Velocity Chart</span>
                    <p className="text-xs text-muted">Transfer timeline visualization</p>
                  </div>
                  <div className="h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart 
                        data={[...selectedAlertDetail.contributing_transactions].sort((a,b) => new Date(a.timestamp) - new Date(b.timestamp))}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" />
                        <XAxis 
                          dataKey="timestamp" 
                          stroke="#64748b" 
                          fontSize={12}
                          tickFormatter={(tick) => tick.split(' ')[1]?.split(':')[0]}
                        />
                        <YAxis stroke="#64748b" fontSize={12} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#16171d', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9', fontSize: '12px', fontWeight: 'bold' }}
                        />
                        <Line 
                          type="monotone" 
                          dataKey="amount" 
                          stroke="#4f46e5" 
                          strokeWidth={2} 
                          activeDot={{ r: 6 }} 
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* User Profile Card */}
              {selectedUserId && selectedUserDetail && (
                <div className="surface-card rounded-xl p-5 text-left shadow-sm bg-surface">
                  <h3 className="text-sm font-bold text-gray-100 mb-4">Customer Profile</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="text-muted text-xs uppercase tracking-wide">KYC Status</div>
                      <div className="font-semibold">{selectedUserDetail.user.kyc_status}</div>
                    </div>
                    <div>
                      <div className="text-muted text-xs uppercase tracking-wide">Risk Score</div>
                      <div className="font-semibold">{Number(selectedUserDetail.user.risk_score).toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-muted text-xs uppercase tracking-wide">Country</div>
                      <div className="font-semibold">{selectedUserDetail.user.country_code}</div>
                    </div>
                    <div>
                      <div className="text-muted text-xs uppercase tracking-wide">IP Address</div>
                      <div className="font-mono text-xs">{selectedUserDetail.user.device_ip}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

      </main>
    </div>
  );
}
