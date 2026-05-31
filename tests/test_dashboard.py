import os
import json
import sys
import threading
import urllib.request
import urllib.error
import pytest
from unittest.mock import patch, MagicMock

from src.dashboard.app import run_server, DashboardRequestHandler, main

@pytest.fixture(scope="module")
def dashboard_server():
    """Start the dashboard server in a background thread for integration testing."""
    # Use a port in the 9000s range to avoid conflict with active local 8000 ports
    server, port = run_server(9000)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield server, port
    server.shutdown()
    server.server_close()
    thread.join()

@pytest.mark.conversion
def test_dashboard_get_index_html(dashboard_server):
    """Verify that requesting the root path or index.html successfully serves HTML content."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/"
    
    # 1. Request root path
    response = urllib.request.urlopen(url)
    assert response.status == 200
    assert "text/html" in response.getheader("Content-Type")
    content = response.read().decode("utf-8")
    assert "Skookum" in content

    # 2. Request index.html explicitly
    response_explicit = urllib.request.urlopen(f"{url}index.html")
    assert response_explicit.status == 200
    assert "text/html" in response_explicit.getheader("Content-Type")

@pytest.mark.conversion
def test_dashboard_get_index_css(dashboard_server):
    """Verify that requesting index.css successfully serves stylesheet content."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/index.css"
    response = urllib.request.urlopen(url)
    assert response.status == 200
    assert "text/css" in response.getheader("Content-Type")
    content = response.read().decode("utf-8")
    assert "body" in content

@pytest.mark.conversion
def test_dashboard_get_index_js(dashboard_server):
    """Verify that requesting index.js successfully serves javascript content."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/index.js"
    response = urllib.request.urlopen(url)
    assert response.status == 200
    assert "javascript" in response.getheader("Content-Type")
    content = response.read().decode("utf-8")
    assert "addEventListener" in content

@pytest.mark.conversion
def test_dashboard_get_api_supported(dashboard_server):
    """Verify that GET /api/supported returns the expected unit registry categories."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/supported"
    response = urllib.request.urlopen(url)
    assert response.status == 200
    assert "application/json" in response.getheader("Content-Type")
    
    data = json.loads(response.read().decode("utf-8"))
    assert data["success"] is True
    assert "categories" in data
    assert "length" in data["categories"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_success(dashboard_server):
    """Verify that POST /api/compute successfully processes a valid mathematical expression conversion."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    payload = json.dumps({
        "expression": "10 m/s * 5 s",
        "target_unit": "foot"
    }).encode("utf-8")

    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    response = urllib.request.urlopen(req)
    assert response.status == 200
    data = json.loads(response.read().decode("utf-8"))
    assert data["success"] is True
    assert "result" in data
    assert "preprocessed" in data
    assert "10 * m/s * 5 * s" in data["preprocessed"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_error_mismatch(dashboard_server):
    """Verify that POST /api/compute returns a 400 client error for dimensional mismatch."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    payload = json.dumps({
        "expression": "10 meter",
        "target_unit": "second"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 400
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["success"] is False
    assert "error" in data
    assert "Dimensional Mismatch" in data["error"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_invalid_json(dashboard_server):
    """Verify that POST /api/compute returns a 400 error for invalid JSON payload."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    payload = b"not-a-json-payload"
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 400
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["success"] is False
    assert "Invalid JSON" in data["error"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_missing_params(dashboard_server):
    """Verify that POST /api/compute returns a 400 error when required parameters are missing."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    payload = json.dumps({
        "expression": "10 meter"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 400
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["success"] is False
    assert "Missing" in data["error"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_empty_body(dashboard_server):
    """Verify that POST /api/compute returns a 400 error for an empty request body."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 400
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["success"] is False
    assert "Empty request body" in data["error"]

@pytest.mark.conversion
def test_dashboard_non_existent_file_404(dashboard_server):
    """Verify that requesting a non-existent static asset file path returns a 404 response."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/nonexistent.html"
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url)
        
    assert exc_info.value.code == 404
    assert "404 Not Found" in exc_info.value.read().decode("utf-8")

@pytest.mark.conversion
def test_dashboard_post_non_existent_api_404(dashboard_server):
    """Verify that POSTing to an unrecognized API path yields a 404 response."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/nonexistent"
    
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 404

@pytest.mark.conversion
def test_dashboard_options_cors(dashboard_server):
    """Verify that sending an OPTIONS request correctly returns 204 No Content for CORS preflight."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    req = urllib.request.Request(url, method="OPTIONS")
    response = urllib.request.urlopen(req)
    assert response.status == 204
    assert response.getheader("Access-Control-Allow-Origin") == "*"
    assert "POST" in response.getheader("Access-Control-Allow-Methods")

@pytest.mark.conversion
def test_dashboard_port_collision_resolution():
    """Verify run_server dynamic port allocation when the starting port is already occupied."""
    # Bind a socket to port 9500 to simulate a collision
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 9500))
    s.listen(1)
    
    try:
        # Run server starting at 9500; it should automatically increment and bind to 9501
        server, active_port = run_server(9500)
        assert active_port == 9501
        server.server_close()
    finally:
        s.close()

@pytest.mark.conversion
def test_dashboard_port_allocation_exhaustion_raises_system_exit():
    """Verify run_server exits cleanly when port range allocation is fully exhausted."""
    with patch("src.dashboard.app.ThreadingHTTPServer", side_effect=OSError("Port in use")):
        with pytest.raises(SystemExit) as exc_info:
            run_server(8000)
        assert exc_info.value.code == 1

@pytest.mark.conversion
def test_dashboard_main_keyboard_interrupt():
    """Verify that keyboard interrupt in serve_forever triggers clean exit without crashing."""
    mock_server = MagicMock()
    mock_server.serve_forever.side_effect = KeyboardInterrupt()
    
    with patch("src.dashboard.app.run_server", return_value=(mock_server, 8000)):
        with patch("sys.argv", ["app.py", "8000"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_server.server_close.assert_called_once()

@pytest.mark.conversion
def test_dashboard_main_argv_invalid_port():
    """Verify that main handles invalid command line argument ports gracefully by defaulting."""
    mock_server = MagicMock()
    with patch("src.dashboard.app.run_server", return_value=(mock_server, 8000)) as mock_run:
        with patch("sys.argv", ["app.py", "invalid-port"]):
            # Suppress serve_forever blocking
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            with pytest.raises(SystemExit):
                main()
            # Verify it defaulted back to 8000
            mock_run.assert_called_once_with(8000)

@pytest.mark.conversion
def test_dashboard_get_api_supported_internal_error(dashboard_server):
    """Verify that GET /api/supported handles registry/serialization internal errors gracefully."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/supported"
    
    with patch("src.dashboard.app.list_supported_units", side_effect=Exception("Database down")):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url)
        assert exc_info.value.code == 500
        data = json.loads(exc_info.value.read().decode("utf-8"))
        assert data["success"] is False
        assert "Internal registry failure" in data["error"]

@pytest.mark.conversion
def test_dashboard_post_api_compute_internal_error(dashboard_server):
    """Verify that POST /api/compute handles parser/engine internal exceptions with 500 status."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/compute"
    
    payload = json.dumps({
        "expression": "10 meter",
        "target_unit": "meter"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with patch("src.dashboard.app.dimensional_compute", side_effect=Exception("Parser crashed")):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 500
        data = json.loads(exc_info.value.read().decode("utf-8"))
        assert data["success"] is False
        assert "Unexpected server failure" in data["error"]

@pytest.mark.conversion
def test_dashboard_get_file_missing_on_disk(dashboard_server):
    """Verify that GET returns 404 Not Found if a recognized static asset path does not exist on disk."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/index.css"
    
    # Mock os.path.exists to return False to simulate a missing file
    with patch("os.path.exists", return_value=False):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url)
        assert exc_info.value.code == 404
        assert "Static asset missing" in exc_info.value.read().decode("utf-8")

@pytest.mark.conversion
def test_dashboard_get_file_read_error(dashboard_server):
    """Verify that GET returns 500 Internal Server Error when opening/reading an asset fails."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/index.css"
    
    # Mock open to raise PermissionError/OSError
    with patch("builtins.open", side_effect=PermissionError("Access Denied")):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url)
        assert exc_info.value.code == 500
        assert "500 Internal Server Error" in exc_info.value.read().decode("utf-8")

@patch("http.server.BaseHTTPRequestHandler.log_message")
def test_dashboard_log_message_not_in_pytest(mock_log):
    """Verify that log_message delegates to parent class when pytest is absent from sys.modules."""
    mock_self = MagicMock(spec=DashboardRequestHandler)
    real_modules = sys.modules.copy()
    if "pytest" in real_modules:
        del real_modules["pytest"]
    
    with patch("sys.modules", real_modules):
        DashboardRequestHandler.log_message(mock_self, "format %s", "arg1")
        mock_log.assert_called_once_with("format %s", "arg1")

@pytest.mark.conversion
def test_dashboard_main_valid_port():
    """Verify that main handles a valid port command line argument correctly."""
    mock_server = MagicMock()
    with patch("src.dashboard.app.run_server", return_value=(mock_server, 8080)) as mock_run:
        with patch("sys.argv", ["app.py", "8080"]):
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            with pytest.raises(SystemExit):
                main()
            mock_run.assert_called_once_with(8080)

@pytest.mark.conversion
def test_dashboard_main_no_argv():
    """Verify that main handles empty/default command line arguments correctly."""
    mock_server = MagicMock()
    with patch("src.dashboard.app.run_server", return_value=(mock_server, 8000)) as mock_run:
        with patch("sys.argv", ["app.py"]):
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            with pytest.raises(SystemExit):
                main()
            mock_run.assert_called_once_with(8000)

@pytest.mark.conversion
def test_dashboard_sys_path_insertion_coverage():
    """Verify that sys.path project root pre-check triggers correctly when absent."""
    import importlib
    import sys
    from src.dashboard.app import PROJECT_ROOT
    
    real_path = sys.path.copy()
    try:
        while PROJECT_ROOT in sys.path:
            sys.path.remove(PROJECT_ROOT)
        
        # Reload the module to force re-execution of module-level path insertion code
        importlib.reload(sys.modules["src.dashboard.app"])
        assert sys.path[0] == PROJECT_ROOT
    finally:
        sys.path = real_path


@pytest.mark.conversion
def test_run_verification_pipeline_mass_addition():
    """Verify that run_verification_pipeline correctly extracts and computes custom mass addition claims."""
    from src.dashboard.app import run_verification_pipeline
    text = "Discrepancy Report: Combining 2kg of HCl with 20000 g of NaOH gave 40,000 g of brine."
    report = run_verification_pipeline("kinematics", text)
    
    assert report["status"] == "discrepancy"
    assert report["formula"] == "2 kg + 20000 g"
    assert report["target"] == "g"
    assert report["claimed"] == "40000 g"
    assert "22000 gram" in report["result"]
    assert "81.82%" in report["report"]


@pytest.mark.conversion
def test_run_verification_pipeline_coordinate_violation():
    """Verify that run_verification_pipeline correctly handles coordinate violations and returns a blocked status."""
    from src.dashboard.app import run_verification_pipeline
    text = "Shift temperature: 30 degC + 10 degC resulting in 40 degC."
    report = run_verification_pipeline("reactor", text)
    
    assert report["status"] == "violation"
    assert "Absolute Coordinate Violation" in report["report"]
    assert "delta_degC" in report["report"]


@pytest.mark.conversion
def test_dashboard_post_api_verify_success(dashboard_server):
    """Verify that POST /api/verify correctly handles client telemetry submissions and returns a trace report."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/verify"
    
    payload = json.dumps({
        "scenario": "kinematics",
        "text": "Discrepancy Report: Combining 2kg of HCl with 20000 g of NaOH gave 40,000 g of brine."
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    response = urllib.request.urlopen(req)
    assert response.status == 200
    data = json.loads(response.read().decode("utf-8"))
    
    assert data["success"] is True
    assert "report" in data
    assert data["report"]["status"] == "discrepancy"
    assert data["report"]["formula"] == "2 kg + 20000 g"


@pytest.mark.conversion
def test_dashboard_post_api_verify_empty_body(dashboard_server):
    """Verify that POST /api/verify returns 400 error for empty request body."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/verify"
    
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
        
    assert exc_info.value.code == 400
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["success"] is False
    assert "Empty request body" in data["error"]


@pytest.mark.conversion
def test_dashboard_post_api_verify_internal_error(dashboard_server):
    """Verify that POST /api/verify returns 500 error on unexpected pipeline exceptions."""
    server, port = dashboard_server
    url = f"http://127.0.0.1:{port}/api/verify"
    
    payload = json.dumps({
        "scenario": "kinematics",
        "text": "10 m"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with patch("src.dashboard.app.run_verification_pipeline", side_effect=Exception("Database failure")):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 500
        data = json.loads(exc_info.value.read().decode("utf-8"))
        assert data["success"] is False
        assert "Agent pipeline failure" in data["error"]



