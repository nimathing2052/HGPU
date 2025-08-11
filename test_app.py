#!/usr/bin/env python3
"""
Unit tests for the Hertie GPU Server Automation App
"""

import unittest
import tempfile
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import json

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import GPUServerManager, parse_container_list, find_available_flask_port

class TestGPUServerManager(unittest.TestCase):
    """Test cases for GPUServerManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = GPUServerManager("test@example.com", "password123")
    
    def test_init(self):
        """Test GPUServerManager initialization"""
        self.assertEqual(self.manager.email, "test@example.com")
        self.assertEqual(self.manager.password, "password123")
        self.assertIsNone(self.manager.ssh_client)
    
    @patch('paramiko.SSHClient')
    def test_connect_ssh_success(self, mock_ssh_client):
        """Test successful SSH connection"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        mock_client.connect.return_value = None
        
        result = self.manager.connect_ssh()
        
        self.assertTrue(result)
        mock_client.connect.assert_called_once()
        self.assertEqual(self.manager.ssh_client, mock_client)
    
    @patch('paramiko.SSHClient')
    def test_connect_ssh_failure(self, mock_ssh_client):
        """Test failed SSH connection"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection failed")
        
        result = self.manager.connect_ssh()
        
        self.assertFalse(result)
        self.assertIsNone(self.manager.ssh_client)
    
    @patch('paramiko.SSHClient')
    def test_execute_command_success(self, mock_ssh_client):
        """Test successful command execution"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        # Mock the SSH connection
        self.manager.ssh_client = mock_client
        
        # Mock the command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b"Command output"
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        success, output = self.manager.execute_command("test command")
        
        self.assertTrue(success)
        self.assertEqual(output, "Command output")
        mock_client.exec_command.assert_called_once_with("test command")
    
    @patch('paramiko.SSHClient')
    def test_execute_command_failure(self, mock_ssh_client):
        """Test failed command execution"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        # Mock the SSH connection
        self.manager.ssh_client = mock_client
        
        # Mock the command execution with error
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"Error message"
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        success, output = self.manager.execute_command("test command")
        
        self.assertFalse(success)
        self.assertEqual(output, "Error message")
    
    def test_disconnect_ssh(self):
        """Test SSH disconnection"""
        mock_client = Mock()
        self.manager.ssh_client = mock_client
        
        self.manager.disconnect_ssh()
        
        mock_client.close.assert_called_once()
        self.assertIsNone(self.manager.ssh_client)
    
    def test_disconnect_ssh_no_client(self):
        """Test SSH disconnection when no client exists"""
        self.manager.ssh_client = None
        
        # Should not raise an exception
        self.manager.disconnect_ssh()
        
        self.assertIsNone(self.manager.ssh_client)

class TestParseContainerList(unittest.TestCase):
    """Test cases for parse_container_list function"""
    
    def test_parse_valid_container_list(self):
        """Test parsing valid container list output"""
        output = """Available ml-containers are:
CONTAINER          FRAMEWORK           STATUS
[test-container]   Tensorflow-2.11.0   Created
[nima-container]   Tensorflow-2.14.0   Up 9 hours
[mx-container]     Mxnet-1.5.0         Exited (137) 1 day ago"""
        
        containers = parse_container_list(output)
        
        self.assertEqual(len(containers), 3)
        self.assertEqual(containers[0]['name'], 'test-container')
        self.assertEqual(containers[0]['framework'], 'Tensorflow-2.11.0')
        self.assertEqual(containers[0]['status'], 'Created')
        
        self.assertEqual(containers[1]['name'], 'nima-container')
        self.assertEqual(containers[1]['framework'], 'Tensorflow-2.14.0')
        self.assertEqual(containers[1]['status'], 'Up 9 hours')
    
    def test_parse_empty_output(self):
        """Test parsing empty output"""
        output = ""
        containers = parse_container_list(output)
        self.assertEqual(containers, [])
    
    def test_parse_no_containers(self):
        """Test parsing output with no containers"""
        output = """Available ml-containers are:
CONTAINER          FRAMEWORK           STATUS"""
        
        containers = parse_container_list(output)
        self.assertEqual(containers, [])
    
    def test_parse_malformed_output(self):
        """Test parsing malformed output"""
        output = """Some random text
that doesn't match the expected format"""
        
        containers = parse_container_list(output)
        self.assertEqual(containers, [])

class TestFindAvailableFlaskPort(unittest.TestCase):
    """Test cases for find_available_flask_port function"""
    
    @patch('subprocess.run')
    def test_find_available_port_success(self, mock_run):
        """Test finding an available port"""
        # Mock that port 2344 is available
        mock_run.return_value.returncode = 1  # lsof returns 1 when port is not in use
        
        port = find_available_flask_port()
        
        self.assertEqual(port, 2344)
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_find_available_port_fallback(self, mock_run):
        """Test finding an available port when default is busy"""
        # Mock that port 2344 is busy, but 2345 is available
        def mock_run_side_effect(*args, **kwargs):
            mock_result = Mock()
            if '2344' in args[0]:
                mock_result.returncode = 0  # Port is in use
            else:
                mock_result.returncode = 1  # Port is available
            return mock_result
        
        mock_run.side_effect = mock_run_side_effect
        
        port = find_available_flask_port()
        
        # Should find the next available port
        self.assertGreater(port, 2344)
        self.assertLess(port, 2400)

class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_manager_lifecycle(self):
        """Test complete manager lifecycle"""
        manager = GPUServerManager("test@example.com", "password123")
        
        # Test initialization
        self.assertEqual(manager.email, "test@example.com")
        self.assertEqual(manager.password, "password123")
        self.assertIsNone(manager.ssh_client)
        
        # Test disconnection without connection (should not fail)
        manager.disconnect_ssh()
        self.assertIsNone(manager.ssh_client)

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
