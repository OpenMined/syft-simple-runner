"use client";

import { useEffect, useState } from "react";
import { apiService, JobHistoryItem, StatusResponse, JobStatsResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Play, CheckCircle, XCircle, Clock, Activity, Eye, Trash2, RefreshCw } from "lucide-react";

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleString();
  } catch {
    return dateString;
  }
}

function formatDuration(seconds?: number): string {
  if (!seconds) return "N/A";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
      return 'bg-green-100 text-green-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    case 'running':
      return 'bg-blue-100 text-blue-800';
    case 'pending':
      return 'bg-yellow-100 text-yellow-800';
    case 'rejected':
      return 'bg-gray-100 text-gray-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

function getStatusIcon(status: string) {
  switch (status.toLowerCase()) {
    case 'completed':
      return <CheckCircle className="h-4 w-4" />;
    case 'failed':
      return <XCircle className="h-4 w-4" />;
    case 'running':
      return <Play className="h-4 w-4" />;
    case 'pending':
      return <Clock className="h-4 w-4" />;
    default:
      return <Activity className="h-4 w-4" />;
  }
}

export function JobHistoryView() {
  const [jobs, setJobs] = useState<JobHistoryItem[]>([]);
  const [stats, setStats] = useState<JobStatsResponse | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<JobHistoryItem | null>(null);
  const [jobLogs, setJobLogs] = useState<string>("");
  const [showLogs, setShowLogs] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const loadData = async () => {
    try {
      const [jobsData, statsData, statusData] = await Promise.all([
        apiService.getJobHistory(50, statusFilter === "all" ? undefined : statusFilter),
        apiService.getJobStats(),
        apiService.getStatus(),
      ]);
      
      setJobs(jobsData.jobs);
      setStats(statsData);
      setStatus(statusData);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewLogs = async (job: JobHistoryItem) => {
    setSelectedJob(job);
    setShowLogs(true);
    try {
      const logsData = await apiService.getJobLogs(job.uid);
      setJobLogs(logsData.logs);
    } catch (error) {
      console.error("Failed to load logs:", error);
      setJobLogs("Failed to load logs");
    }
  };

  const handleCleanup = async () => {
    try {
      await apiService.cleanupJobHistory(30);
      loadData(); // Reload data after cleanup
    } catch (error) {
      console.error("Failed to cleanup history:", error);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Card className="animate-pulse">
          <CardHeader>
            <div className="h-6 bg-muted rounded w-1/3"></div>
            <div className="h-4 bg-muted rounded w-2/3"></div>
          </CardHeader>
          <CardContent>
            <div className="h-20 bg-muted rounded"></div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center">
          <Activity className="mr-3 h-8 w-8" />
          Syft Simple Runner
        </h1>
        <p className="text-muted-foreground mt-2">
          Job execution history and monitoring
        </p>
      </div>

      {/* Status Card */}
      {status && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Activity className="mr-2 h-5 w-5" />
              Application Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Version:</span> {status.version}
              </div>
              <div>
                <span className="font-medium">User:</span> {status.syftbox.user_email}
              </div>
              <div>
                <span className="font-medium">Runner:</span>{" "}
                <Badge variant="outline" className="ml-1">
                  {status.components.runner}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Job History:</span>{" "}
                <Badge variant="outline" className="ml-1">
                  {status.components.job_history}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Card */}
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle>Job Statistics</CardTitle>
            <CardDescription>
              Overall performance and execution metrics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{stats.total_jobs}</div>
                <div className="text-sm text-muted-foreground">Total Jobs</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{stats.successful_jobs}</div>
                <div className="text-sm text-muted-foreground">Successful</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{stats.failed_jobs}</div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{stats.success_rate}%</div>
                <div className="text-sm text-muted-foreground">Success Rate</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Job History Card */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center">
                <Eye className="mr-2 h-5 w-5" />
                Job Execution History
              </CardTitle>
              <CardDescription>
                Recent job executions and their status
              </CardDescription>
            </div>
            <div className="flex space-x-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-1 border rounded-md text-sm"
              >
                <option value="all">All Status</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="running">Running</option>
                <option value="pending">Pending</option>
              </select>
              <Button onClick={loadData} size="sm" variant="outline">
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button onClick={handleCleanup} size="sm" variant="outline">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No job execution history found. Jobs will appear here once they've been executed.
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.uid}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(job.status)}
                      <Badge className={getStatusColor(job.status)}>
                        {job.status}
                      </Badge>
                    </div>
                    <div>
                      <div className="font-medium">{job.name}</div>
                      <div className="text-sm text-muted-foreground">
                        From: {job.requester_email}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                    <div>
                      {job.completed_at ? formatDate(job.completed_at) : formatDate(job.created_at)}
                    </div>
                    <div>
                      Duration: {formatDuration(job.execution_time)}
                    </div>
                    <Button
                      onClick={() => handleViewLogs(job)}
                      size="sm"
                      variant="outline"
                    >
                      View Logs
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Logs Modal */}
      {showLogs && selectedJob && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">
                  Execution Logs: {selectedJob.name}
                </h2>
                <Button
                  onClick={() => setShowLogs(false)}
                  variant="outline"
                  size="sm"
                >
                  Close
                </Button>
              </div>
            </div>
            <div className="p-6 overflow-auto max-h-96">
              <pre className="text-sm bg-gray-100 p-4 rounded-md overflow-auto">
                {jobLogs}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 