# Hertie GPU Server Automation Flask App

A comprehensive web-based automation tool for managing GPU containers and Jupyter notebooks on the Hertie School GPU server. This application provides an intuitive interface for container lifecycle management, automatic GPU optimization, and seamless Jupyter notebook access.

## ✨ Key Features

- 🔐 **Secure Authentication**: SSH-based authentication to the GPU server
- 📦 **Complete Container Management**: Create, start, stop, and **remove** ML containers
- 🚀 **Smart Jupyter Integration**: Launch Jupyter notebooks with automatic port forwarding and **no authentication required**
- 🎯 **Intelligent GPU Selection**: Automatically selects the **least loaded GPU** based on utilization and memory usage
- 🌐 **Modern Web Interface**: Responsive, animated UI with real-time progress tracking
- 🔄 **Robust Session Management**: Persistent sessions with automatic cleanup and port management
- 🧹 **Advanced Cleanup Tools**: Port cleanup and session management utilities
- ⚡ **Real-time Progress Tracking**: Visual progress indicators for container creation and Jupyter launches

## 🚀 Recent Enhancements

### Container Management Improvements
- ✅ **Container Removal**: Interactive container removal with confirmation
- ✅ **Loading Animations**: Visual feedback during container creation and operations
- ✅ **Enhanced UI**: Improved layout with better session ID visibility
- ✅ **Progress Tracking**: Real-time progress modal for Jupyter launches

### GPU Optimization
- ✅ **Smart GPU Selection**: Automatically finds GPU with lowest utilization
- ✅ **GPU Information Display**: Shows which specific GPU is being used
- ✅ **Resource Monitoring**: Tracks GPU utilization and memory usage

### User Experience
- ✅ **No Authentication Required**: Jupyter notebooks launch without token/password
- ✅ **Auto-expanding Progress Modal**: Dynamic UI that adapts to operation steps
- ✅ **Session Persistence**: Maintains connections across browser sessions
- ✅ **Error Handling**: Comprehensive error messages and recovery

## 📋 Prerequisites

- Python 3.8 or higher
- SSH access to the Hertie GPU server (10.1.23.20)
- Network access to the server
- Modern web browser with JavaScript enabled

## 🛠️ Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application** (optional):
   - Edit `config.py` to modify server settings, ports, or timeouts
   - Default configuration is optimized for the Hertie GPU server

## 🎯 Usage

### Starting the Application

1. **Run the Flask app**:
   ```bash
   python app.py
   ```

2. **Access the web interface**:
   - Open your browser and go to `http://localhost:2344`
   - The app automatically finds an available port if 2344 is busy
   - Current port is displayed in the console output

### Using the Web Interface

#### 1. **Authentication**
- Enter your Hertie School email and password
- Click "Authenticate" to establish SSH connection
- Session ID is displayed in the header for reference

#### 2. **Container Management**
- **View Containers**: See all your containers with status, framework, and version
- **Create Containers**: 
  - Choose from TensorFlow, PyTorch, or MXNet
  - Select specific versions
  - Real-time loading animation during creation
- **Start/Stop Containers**: Manage container states
- **Remove Containers**: Interactive removal with confirmation dialog

#### 3. **Jupyter Notebooks**
- Click "🌐 Launch Jupyter" on any running container
- Watch real-time progress with detailed steps:
  - Container startup
  - GPU selection (shows specific GPU number)
  - Environment setup
  - Port forwarding
- Jupyter opens automatically in a new tab
- **No authentication required** - direct access

#### 4. **Session Management**
- **Session ID**: Visible in header for reference
- **Cleanup Ports**: Clean up SSH tunnels while keeping session
- **Logout**: Complete session cleanup

## ⚙️ Configuration

### Server Settings (`config.py`)

```python
# Server Configuration
SERVER_HOST = "10.1.23.20"  # GPU server IP
SERVER_PORT = 22            # SSH port

# Local Port Configuration
LOCAL_PORT_RANGE = range(9000, 9100)  # Ports for Jupyter forwarding

# Flask App Configuration
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 2344
FLASK_DEBUG = False
```

### Supported Frameworks & Versions

- **TensorFlow**: 2.11.0, 2.10.0, 2.9.2-jlab, 2.9.0, 2.8.0, 2.7.0, 2.6.1, 2.5.0, 2.4.1, 2.4.0, 2.3.1-nvidia, 1.15.4-nvidia
- **PyTorch**: 2.1.0-aime, 2.1.0, 2.0.1-aime, 2.0.1, 2.0.0, 1.14.0a-nvidia, 1.13.1-aime, 1.13.0a-nvidia, 1.12.1-aime
- **MXNet**: 1.8.0-nvidia

## 🏗️ Architecture

### Core Components

- **`app.py`**: Main Flask application with all routes and business logic
- **`GPUServerManager`**: Advanced class handling SSH connections, container operations, and GPU optimization
- **`templates/`**: Modern HTML templates with JavaScript for interactive UI
- **`config.py`**: Configuration settings and server parameters
- **Test Files**: Comprehensive test suite for all functionality

### Key Features Implementation

1. **SSH Connection Management**:
   - Secure connection to GPU server with keepalive
   - Interactive command support (for container removal)
   - Automatic connection cleanup and error handling

2. **Container Operations**:
   - Container creation with framework/version selection
   - Start/stop container management
   - **Interactive container removal** with confirmation
   - Real-time status monitoring

3. **Jupyter Integration**:
   - Automatic Jupyter startup in containers
   - Port forwarding setup with automatic port discovery
   - **Authentication disabled** for seamless access
   - Progress tracking with detailed steps

4. **GPU Optimization**:
   - **Automatic GPU selection** based on utilization and memory
   - Real-time GPU usage monitoring
   - Display of selected GPU information

5. **Session Management**:
   - Persistent user sessions with timeout
   - Automatic session cleanup
   - Port management and cleanup utilities

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Main functionality tests
python test_app.py

# Container removal tests
python test_container_removal.py

# SSH connection tests
python test_ssh_manual.py
```

The test suite includes:
- SSH connection and authentication tests
- Container management (create, start, stop, **remove**) tests
- Jupyter launch and GPU selection tests
- Utility function tests
- Flask app integration tests

## 🔧 Troubleshooting

### Common Issues

1. **SSH Connection Failed**:
   - Verify your credentials (N.Thing@students.hertie-school.org)
   - Check network connectivity to 10.1.23.20
   - Ensure SSH access is enabled

2. **Port Already in Use**:
   - The app automatically finds available ports (9000-9099)
   - Check if another instance is running
   - Use "Cleanup Ports" button to clear orphaned connections

3. **Container Creation Failed**:
   - Verify framework and version combinations
   - Check server resources
   - Ensure container name is unique
   - Watch for loading animation and error messages

4. **Jupyter Not Starting**:
   - Check if container is running
   - Verify port forwarding setup
   - Check progress modal for specific error steps
   - Ensure no firewall blocking local ports

5. **Container Removal Issues**:
   - Containers must be stopped before removal
   - Use interactive confirmation (Y/N)
   - Check for running processes in container

### Debug Mode

Enable debug mode in `config.py`:
```python
FLASK_DEBUG = True
```

This provides detailed error messages and auto-reload on code changes.

## 🔒 Security Considerations

- SSH passwords stored in memory only during active sessions
- Sessions automatically timeout after 1 hour
- All connections use secure SSH protocol
- **Jupyter authentication disabled** for convenience (use only on trusted networks)
- Interactive container removal requires confirmation

## 📦 Dependencies

- **Flask**: Web framework for the application
- **Paramiko**: SSH client library with interactive support
- **Werkzeug**: WSGI utilities
- **Cryptography**: Security utilities for SSH connections

## 📄 License

This project is developed for internal use at the Hertie School.

## 🆘 Support

For issues or questions:

1. **Check the troubleshooting section** above
2. **Review the test output** for specific errors
3. **Check server logs** for detailed error messages
4. **Verify network connectivity** to the GPU server
5. **Ensure proper credentials** and SSH access

## 🎉 Recent Updates

- ✅ **Container Removal**: Interactive removal with confirmation
- ✅ **GPU Selection**: Automatic selection with specific GPU display
- ✅ **Loading Animations**: Visual feedback for all operations
- ✅ **Progress Tracking**: Real-time progress for Jupyter launches
- ✅ **UI Improvements**: Better layout and session management
- ✅ **Error Handling**: Comprehensive error messages and recovery
