# Hertie GPU Server Automation Flask App

A web-based automation tool for managing GPU containers and Jupyter notebooks on the Hertie School GPU server.

## Features

- 🔐 **Secure Authentication**: SSH-based authentication to the GPU server
- 📦 **Container Management**: Create, start, stop, and manage ML containers
- 🚀 **Jupyter Integration**: Launch Jupyter notebooks with automatic port forwarding
- 🎮 **GPU Optimization**: Automatically selects the least loaded GPU
- 🌐 **Web Interface**: Modern, responsive web UI for easy management
- 🔄 **Session Management**: Persistent sessions with automatic cleanup

## Prerequisites

- Python 3.8 or higher
- SSH access to the Hertie GPU server
- Network access to the server (10.1.23.20)

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application** (optional):
   - Edit `config.py` to modify server settings, ports, or timeouts
   - Default configuration is set for the Hertie GPU server

## Usage

### Starting the Application

1. **Run the Flask app**:
   ```bash
   python app.py
   ```

2. **Access the web interface**:
   - Open your browser and go to `http://localhost:2344`
   - The app will automatically find an available port if 2344 is busy

### Using the Web Interface

1. **Authentication**:
   - Enter your Hertie School email and password
   - Click "Authenticate" to connect to the GPU server

2. **Container Management**:
   - View existing containers
   - Create new containers with different ML frameworks (PyTorch, TensorFlow, JAX, Hugging Face)
   - Start/stop containers as needed

3. **Jupyter Notebooks**:
   - Click "Launch Jupyter" on any running container
   - Jupyter will open in a new browser tab
   - Authentication is automatically disabled for easy access

## Configuration

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

### Supported Frameworks

- **PyTorch**: Latest, 2.1.0, 2.0.1, 1.13.1
- **TensorFlow**: Latest, 2.13.0, 2.12.0, 2.11.0
- **JAX**: Latest, 0.4.13, 0.4.12
- **Hugging Face**: Latest, 4.30.0, 4.29.0

## Architecture

### Core Components

- **`app.py`**: Main Flask application with all routes and business logic
- **`GPUServerManager`**: Class handling SSH connections and container operations
- **`templates/`**: HTML templates for the web interface
- **`config.py`**: Configuration settings
- **`test_app.py`**: Unit tests for core functionality

### Key Features

1. **SSH Connection Management**:
   - Secure connection to GPU server
   - Automatic connection cleanup
   - Error handling and retry logic

2. **Container Operations**:
   - Container creation with framework/version selection
   - Start/stop container management
   - Status monitoring

3. **Jupyter Integration**:
   - Automatic Jupyter startup in containers
   - Port forwarding setup
   - Authentication disabled for easy access

4. **Session Management**:
   - Persistent user sessions
   - Automatic session cleanup
   - Multi-user support

## Testing

Run the test suite to verify functionality:

```bash
python test_app.py
```

The test suite includes:
- SSH connection tests
- Container management tests
- Utility function tests
- Flask app integration tests

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**:
   - Verify your credentials
   - Check network connectivity to the server
   - Ensure SSH access is enabled

2. **Port Already in Use**:
   - The app automatically finds available ports
   - Check if another instance is running

3. **Container Creation Failed**:
   - Verify framework and version combinations
   - Check server resources
   - Ensure container name is unique

4. **Jupyter Not Starting**:
   - Check if container is running
   - Verify port forwarding setup
   - Check server logs for errors

### Debug Mode

Enable debug mode in `config.py`:
```python
FLASK_DEBUG = True
```

This will provide detailed error messages and auto-reload on code changes.

## Security Considerations

- SSH passwords are stored in memory only during active sessions
- Sessions automatically timeout after 1 hour
- All connections use secure SSH protocol
- Jupyter authentication is disabled for convenience (use only on trusted networks)

## Dependencies

- **Flask**: Web framework
- **Paramiko**: SSH client library
- **Werkzeug**: WSGI utilities
- **Cryptography**: Security utilities

## License

This project is developed for internal use at the Hertie School.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the test output
3. Check server logs for detailed error messages
