# Syft Simple Runner

Simple and secure code execution runner for Syft Code Queue with web-based job history monitoring.

## Features

- ✅ **Continuous Job Processing**: Monitors and executes approved code jobs
- 🔒 **Safe Execution**: Validates scripts before execution with security checks
- 📊 **Web Dashboard**: Real-time job history and execution statistics
- 📝 **Detailed Logging**: Comprehensive execution logs for each job
- 🔄 **Auto-cleanup**: Configurable cleanup of old job history
- 📈 **Performance Metrics**: Success rates and execution time tracking

## Web Interface

The runner includes a comprehensive web dashboard that displays:

- **Application Status**: Current runner state and configuration
- **Job Statistics**: Success rates, execution counts, and performance metrics  
- **Job History**: Detailed list of executed jobs with status and timing
- **Execution Logs**: Full logs for each job execution
- **Filtering & Search**: Filter jobs by status (completed, failed, running, etc.)

### Accessing the Web Interface

When deployed as a SyftBox app, the web interface is automatically available at the assigned port. The interface provides:

- Real-time job execution history
- Detailed execution logs and error messages
- Job performance statistics and success rates
- Easy filtering and sorting of job history

## API Endpoints

The runner exposes REST API endpoints for programmatic access:

- `GET /api/status` - Application status and configuration
- `GET /api/v1/jobs/history` - Job execution history
- `GET /api/v1/jobs/stats` - Execution statistics  
- `GET /api/v1/jobs/history/{id}/logs` - Job execution logs
- `DELETE /api/v1/jobs/history/cleanup` - Clean up old job records

## Usage

This app is designed to run as a SyftBox app. It automatically:

1. Monitors for approved code execution jobs
2. Validates and executes jobs safely
3. Logs all execution details and results
4. Provides web interface for monitoring
5. Stores job history for review and analysis

The web interface allows data site operators to monitor job execution performance and troubleshoot any issues.
