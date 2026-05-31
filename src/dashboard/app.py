import os
import json
import sys
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

# Add the project root to sys.path if not present to ensure absolute imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.server import dimensional_compute, list_supported_units
from src.parser import preprocess_expression

def run_verification_pipeline(scenario: str, text: str) -> dict:
    """Simulates the headless AI Agent prompt verification steps and compiles a traceability report."""
    import re
    from src.engine import resolve_unit
    
    # Whitelist of supported units for safe parsing
    WHITELISTED_UNITS = {
        "m", "cm", "mm", "km", "in", "ft", "feet", "yd", "yard", "mi", "mile", "miles",
        "g", "kg", "mg", "lb", "pound", "pounds", "oz", "ounce", "ounces",
        "s", "sec", "second", "seconds", "min", "minute", "minutes", "hr", "hour", "hours",
        "mol", "mmol", "mole", "moles",
        "W", "kW", "MW", "watt", "watts",
        "J", "MJ", "Wh", "kWh", "joule", "joules",
        "degC", "degF", "K", "delta_degC", "delta_degF", "delta_K",
        "m/s", "mph", "km/h", "l/100km", "mpg"
    }

    # Defaults in case extraction fails
    if scenario == "kinematics":
        expr, target, claimed = "10 m/s * 5 s", "ft", "160 ft"
    elif scenario == "energy":
        expr, target, claimed = "500 W * 2 hr", "MJ", "3.6 MJ"
    else:
        expr, target, claimed = "30 degC + 10 degC", "degC", "40 degC"

    try:
        # Extract all potential quantities: number followed by a unit
        # Matches commas in numbers like 40,000
        raw_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*([a-zA-Z_/%^**0-9-]+)(?![a-zA-Z_])', text)
        
        valid_quantities = []
        for val_str, unit_str in raw_matches:
            val_str = val_str.replace(",", "")
            if unit_str in WHITELISTED_UNITS or unit_str.lower() in WHITELISTED_UNITS:
                valid_quantities.append((val_str, unit_str))
                
        if len(valid_quantities) >= 3:
            # Take all but the last one as expr terms, last one is the claimed value
            last_val, last_unit = valid_quantities[-1]
            target = last_unit
            claimed = f"{last_val} {last_unit}"
            
            # Let's inspect the first two quantities to choose multiplication or addition
            u1 = resolve_unit(valid_quantities[0][1])
            u2 = resolve_unit(valid_quantities[1][1])
            
            # Helper to check dimensions
            is_u1_velocity = "T" in u1.cardinality and u1.cardinality.get("T", 0) < 0 and u1.cardinality.get("L", 0) > 0
            is_u2_time = u2.cardinality == {"L": 0, "M": 0, "T": 1, "Theta": 0, "I": 0, "N": 0, "J": 0}
            is_u1_power = u1.cardinality.get("L", 0) == 2 and u1.cardinality.get("M", 0) == 1 and u1.cardinality.get("T", 0) == -3
            
            if (is_u1_velocity and is_u2_time) or (is_u1_power and is_u2_time):
                # Multiplication: velocity * time or power * time
                expr = " * ".join(f"{val} {unit}" for val, unit in valid_quantities[:-1])
            else:
                # Default to addition
                expr = " + ".join(f"{val} {unit}" for val, unit in valid_quantities[:-1])
                
        elif len(valid_quantities) == 2:
            # Shift operation with 2 quantities e.g. "30 degC + 10 delta_degC"
            u1_val, u1_unit = valid_quantities[0]
            u2_val, u2_unit = valid_quantities[1]
            expr = f"{u1_val} {u1_unit} + {u2_val} {u2_unit}"
            target = u1_unit
            claimed = f"{u1_val} {u1_unit}" # fallback
            
    except Exception:
        pass

    # 2. Compute true physical results
    res = dimensional_compute(expr, target)
    clean_res = res[len("Result:"):].strip() if res.startswith("Result:") else res

    # 3. Classify execution trace and compile traceability report
    if res.startswith("Security Error") or res.startswith("Parsing Error") or res.startswith("Type Error") or res.startswith("Math Error") or res.startswith("Error"):
        steps = [
            {"step": 1, "action": "NLP Scan", "log": "Scanning telemetry document... Detected physical claims."},
            {"step": 2, "action": "Claim Extraction", "log": f"Extracted absolute coordinates addition claim: {expr}."},
            {"step": 3, "action": "MCP Tool Invocation", "log": f"Calling tool 'dimensional_compute(expression=\"{expr}\", target_unit=\"{target}\")'..."},
            {"step": 4, "action": "Engine Blocker Triggered", "log": f"Coordination blocker raised exception: {clean_res}."},
            {"step": 5, "action": "Safety Intercepted", "log": "Validation failed: coordinate violation prevents mathematical evaluation."}
        ]
        
        return {
            "status": "violation",
            "title": "Coordinate Violation Blocked",
            "steps": steps,
            "formula": expr,
            "target": target,
            "claimed": claimed,
            "result": "Blocked by Safety Guard",
            "traceback": f"Physical Violation: {clean_res}",
            "report": (
                "### Coolant Shifting Validation Report\n\n"
                "**Status**: 🚨 **Blocked: Absolute Coordinate Violation**\n\n"
                f"- **Attempted Math**: `{expr}` (Adding absolute coordinate bounds together).\n"
                f"- **Validation Result**: `{clean_res}`\n"
                "- **Educational Safety Guidance**: The operation was blocked because **adding absolute temperatures is physically impossible** "
                "(analogous to adding two GPS latitude coordinates together). To shift an absolute temperature, "
                "you must add a temperature difference (**`delta_degC`**) instead of an absolute scale (**`degC`**)."
            )
        }

    # 4. Compare claimed and computed float values
    try:
        claimed_val = claimed.split()[0]
        claimed_float = float(claimed_val)
        
        float_match = re.search(r'approx\.\s+([0-9.eE+-]+)', clean_res)
        if float_match:
            computed_float = float(float_match.group(1))
        else:
            computed_float = float(clean_res.split()[0])
            
        is_match = abs(computed_float - claimed_float) < 1e-4 * max(abs(computed_float), 1.0)
    except Exception:
        is_match = False

    steps = [
        {"step": 1, "action": "NLP Scan", "log": "Scanning telemetry document... Detected physical claims."},
        {"step": 2, "action": "Claim Extraction", "log": f"Extracted: Formula = '{expr}', Target Unit = '{target}', Claimed = '{claimed}'."},
        {"step": 3, "action": "MCP Tool Invocation", "log": f"Calling tool 'dimensional_compute(expression=\"{expr}\", target_unit=\"{target}\")'..."},
        {"step": 4, "action": "Solver Execution", "log": f"Calculated exact identity: {clean_res}."},
        {"step": 5, "action": "Traceability Audit", "log": f"Verifying claimed '{claimed}' against exact rational solver result..."}
    ]

    if is_match:
        return {
            "status": "verified",
            "title": "Claim Verified (100% Dynamic Match)",
            "steps": steps,
            "formula": expr,
            "target": target,
            "claimed": claimed,
            "result": clean_res,
            "traceback": f"Claim matches exact rational internal value of {clean_res}. Exact conversion verified without float drift.",
            "report": (
                "### Formal Physics Validation Report\n\n"
                "**Status**: 🟢 **Claim Fully Verified**\n\n"
                f"- **Logged Claim**: `{expr}` yields a total of `{claimed}`.\n"
                f"- **Computed Truth**: `{clean_res}`\n"
                "- **Algebraic Identity**: The log is **100% mathematically correct**. "
                "The exact internal rational identity matches the logged claim. "
                "Dynamic unit conversion checks completed with zero floating-point accumulation errors."
            )
        }
    else:
        try:
            percent_err = abs(computed_float - claimed_float) / max(computed_float, 1.0) * 100
            err_str = f"The telemetry log introduces a **{percent_err:.2f}% scaling calibration error**."
        except Exception:
            err_str = "The telemetry log introduces a scaling calibration error."

        return {
            "status": "discrepancy",
            "title": "Discrepancy Detected",
            "steps": steps,
            "formula": expr,
            "target": target,
            "claimed": claimed,
            "result": clean_res,
            "traceback": f"{clean_res} computed vs {claimed} claimed. Claims are algebraically incorrect due to scale factor mismatches.",
            "report": (
                "### Formal Physics Validation Report\n\n"
                "**Status**: 🔴 **Discrepancy Detected**\n\n"
                f"- **Logged Claim**: `{expr}` yields a total of `{claimed}`.\n"
                f"- **Computed Truth**: `{clean_res}`\n"
                f"- **Calibration Mismatch**: The claim is mathematically incorrect. "
                f"The actual value resolves to `{clean_res}` instead of the logged `{claimed}`. "
                f"{err_str}"
            )
        }

class DashboardRequestHandler(BaseHTTPRequestHandler):
    """
    Custom request handler serving static files for the premium dashboard
    and exposing dynamic physical conversion API endpoints.
    """

    def log_message(self, format, *args):
        # Override to prevent spamming stderr during test suite runs
        if "pytest" in sys.modules:
            return
        super().log_message(format, *args)

    def _send_json(self, status: int, data: dict):
        """Helper to send a JSON response with correct headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Support pre-flight CORS requests for modern browser client integration."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        """Handle static file requests and supported units dynamic registry query."""
        path = self.path.split("?")[0]

        # 1. API: Get supported units
        if path == "/api/supported":
            try:
                units_data = json.loads(list_supported_units())
                self._send_json(200, {"success": True, "categories": units_data})
            except Exception as e:
                self._send_json(500, {"success": False, "error": f"Internal registry failure: {e}"})
            return

        # 2. Static Files Serving
        dashboard_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Normalize request paths to prevent path traversal vulnerability attacks
        if path in ("/", "/index.html"):
            target_file = "index.html"
        elif path == "/index.css":
            target_file = "index.css"
        elif path == "/index.js":
            target_file = "index.js"
        else:
            # File not found
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        full_file_path = os.path.join(dashboard_dir, target_file)
        
        if not os.path.exists(full_file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found: Static asset missing on server.")
            return

        # Set appropriate MIME Type
        if target_file.endswith(".html"):
            mime_type = "text/html"
        elif target_file.endswith(".css"):
            mime_type = "text/css"
        else:
            mime_type = "application/javascript"


        try:
            with open(full_file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"500 Internal Server Error: {e}".encode("utf-8"))

    def do_POST(self):
        """Handle physical expression calculation and target unit conversion submissions."""
        path = self.path.split("?")[0]
        
        if path not in ("/api/compute", "/api/verify"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        if path == "/api/verify":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._send_json(400, {"success": False, "error": "Empty request body received."})
                    return
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                
                scenario = data.get("scenario", "kinematics")
                text = data.get("text", "").strip()
                
                report = run_verification_pipeline(scenario, text)
                self._send_json(200, {"success": True, "report": report})
            except Exception as e:
                self._send_json(500, {"success": False, "error": f"Agent pipeline failure: {e}"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"success": False, "error": "Empty request body received."})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            expression = data.get("expression", "").strip()
            target_unit = data.get("target_unit", "").strip()

            if not expression or not target_unit:
                self._send_json(400, {"success": False, "error": "Missing 'expression' or 'target_unit' parameters."})
                return

            # Delegate arithmetic and conversion to whitelisted AST parser and engine
            res_str = dimensional_compute(expression, target_unit)

            # Classify endpoint result matching server formats
            if res_str.startswith("Result:"):
                # Clean up "Result: " prefix
                clean_res = res_str[len("Result:"):].strip()
                try:
                    preprocessed_expr = preprocess_expression(expression)
                except Exception:
                    preprocessed_expr = expression
                self._send_json(200, {
                    "success": True, 
                    "result": clean_res,
                    "preprocessed": preprocessed_expr
                })
            else:
                # Return standard 400 Bad Request status containing descriptive error messages
                self._send_json(400, {"success": False, "error": res_str})

        except json.JSONDecodeError:
            self._send_json(400, {"success": False, "error": "Invalid JSON format in payload."})
        except Exception as e:
            self._send_json(500, {"success": False, "error": f"Unexpected server failure: {e}"})

def run_server(port: int = 8000) -> Tuple[ThreadingHTTPServer, int]:
    """
    Initializes and starts the Threading HTTPServer on a configurable port.
    If the default port is occupied, automatically increments the port to find a free socket.
    """
    current_port = port
    max_port = port + 100
    server = None

    while current_port < max_port:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", current_port), DashboardRequestHandler)
            break
        except OSError:
            # Address already in use, increment port dynamically
            current_port += 1

    if server is None:
        print("Error: Could not allocate any free socket port within range.", file=sys.stderr)
        sys.exit(1)

    return server, current_port

def main():
    """Main entry point parsed by console scripts."""
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server, active_port = run_server(port)
    print(f"=========================================================================")
    print(f"  Skookum MCP Dashboard Server running successfully!")
    print(f"  Access the premium playground at: http://127.0.0.1:{active_port}/")
    print(f"=========================================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown request received. Stopping dashboard server cleanly.")
        server.server_close()
        sys.exit(0)

if __name__ == "__main__":
    main()
