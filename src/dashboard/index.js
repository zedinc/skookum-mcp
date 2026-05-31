/* ==========================================================================
   ANTIGRAVITY UNITS PLAYGROUND - CLIENT-SIDE INTERACTIVE ENGINE
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // ----------------------------------------------------------------------
    // DOM Element Selections
    // ----------------------------------------------------------------------
    const solverForm = document.getElementById("solver-form");
    const expressionInput = document.getElementById("expression-input");
    const targetUnitInput = document.getElementById("target-unit-input");
    const clearInputBtn = document.getElementById("clear-input-btn");
    const submitBtn = document.getElementById("submit-btn");
    const submitSpinner = submitBtn.querySelector(".loading-spinner");
    
    // Result panels
    const emptyState = document.getElementById("results-empty-state");
    const successCard = document.getElementById("results-success-card");
    const errorCard = document.getElementById("results-error-card");
    
    // Success values
    const answerApprox = document.getElementById("answer-approx");
    const answerUnit = document.getElementById("answer-unit");
    const metricExact = document.getElementById("metric-exact");
    const metricInternal = document.getElementById("metric-internal");
    const metricDim = document.getElementById("metric-dim");
    
    // Timeline steps
    const stepToken = document.getElementById("step-token");
    const stepCoord = document.getElementById("step-coord");
    const stepScale = document.getElementById("step-scale");
    
    // Error values
    const errorCategory = document.getElementById("error-category");
    const errorMessage = document.getElementById("error-message");
    const errorTipsList = document.getElementById("error-tips");
    
    // History & Palette
    const accordionContainer = document.getElementById("units-accordion");
    const historyContainer = document.getElementById("history-container");
    const clearHistoryBtn = document.getElementById("clear-history-btn");

    // State Variables
    let lastFocusedInput = expressionInput;
    let unitsRegistry = {};

    // ----------------------------------------------------------------------
    // Last Focused Input Tracker (for visual badge injection)
    // ----------------------------------------------------------------------
    expressionInput.addEventListener("focus", () => lastFocusedInput = expressionInput);
    targetUnitInput.addEventListener("focus", () => lastFocusedInput = targetUnitInput);

    // Clear Expression Button
    clearInputBtn.addEventListener("click", () => {
        expressionInput.value = "";
        expressionInput.focus();
    });

    // ----------------------------------------------------------------------
    // Cursor Insertion Helper
    // ----------------------------------------------------------------------
    function insertAtCursor(inputEl, text) {
        const startPos = inputEl.selectionStart;
        const endPos = inputEl.selectionEnd;
        const oldVal = inputEl.value;
        
        // Add a leading space if needed to prevent token collision
        const prefix = (startPos > 0 && oldVal[startPos - 1] !== " " && text !== "%") ? " " : "";
        const suffix = (endPos < oldVal.length && oldVal[endPos] !== " ") ? " " : "";
        const insertText = prefix + text + suffix;

        inputEl.value = oldVal.substring(0, startPos) + insertText + oldVal.substring(endPos, oldVal.length);
        
        // Put focus back and place cursor immediately after inserted text
        inputEl.focus();
        const newCursorPos = startPos + insertText.length;
        inputEl.setSelectionRange(newCursorPos, newCursorPos);
        
        // Trigger input event to let dynamic frameworks/handlers know of changes
        inputEl.dispatchEvent(new Event("input", { bubbles: true }));
    }

    // ----------------------------------------------------------------------
    // Fetch and Build supported units registry visual builder palette
    // ----------------------------------------------------------------------
    async function fetchSupportedUnits() {
        try {
            const res = await fetch("/api/supported");
            const data = await res.json();
            
            if (data.success && data.categories) {
                unitsRegistry = data.categories;
                buildUnitsAccordion(data.categories);
            } else {
                showPaletteError("Failed to resolve unit categories registry.");
            }
        } catch (e) {
            showPaletteError(`Failed to connect to registry API: ${e.message}`);
        }
    }

    function showPaletteError(msg) {
        accordionContainer.innerHTML = `
            <div class="palette-loading" style="color: var(--danger)">
                <span>&#9888; ${msg}</span>
            </div>
        `;
    }

    function buildUnitsAccordion(categories) {
        accordionContainer.innerHTML = "";
        
        // Format names nicely for visual aesthetics
        const categoryLabels = {
            "length": "Length (L)",
            "mass": "Mass (M)",
            "time": "Time (T)",
            "temperature": "Temperature (Theta)",
            "velocity": "Velocity (L/T)",
            "force": "Force (M*L/T^2)",
            "energy": "Energy (M*L^2/T^2)",
            "power": "Power (M*L^2/T^3)",
            "pressure": "Pressure & Stress",
            "dimensionless": "Dimensionless & Angles"
        };

        for (const [key, units] of Object.entries(categories)) {
            const label = categoryLabels[key] || key.replace("_", " ");
            
            const accordionItem = document.createElement("div");
            accordionItem.className = "accordion-item";
            
            const trigger = document.createElement("button");
            trigger.type = "button";
            trigger.className = "accordion-trigger";
            trigger.innerHTML = `
                <span>${label}</span>
                <span class="accordion-icon">&#9656;</span>
            `;
            
            const content = document.createElement("div");
            content.className = "accordion-content";
            
            const badgesGroup = document.createElement("div");
            badgesGroup.className = "badges-group";
            
            units.forEach(unitStr => {
                // Extract symbol abbreviation e.g. "meter (m)" -> "m"
                const match = unitStr.match(/\(([^)]+)\)/);
                const symbol = match ? match[1] : unitStr;
                
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "unit-badge-btn";
                btn.textContent = unitStr;
                btn.title = `Inject '${symbol}'`;
                
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    insertAtCursor(lastFocusedInput, symbol);
                });
                
                badgesGroup.appendChild(btn);
            });
            
            content.appendChild(badgesGroup);
            accordionItem.appendChild(trigger);
            accordionItem.appendChild(content);
            
            // Toggle active state
            trigger.addEventListener("click", () => {
                const isActive = accordionItem.classList.contains("active");
                
                // Collapse all other items
                document.querySelectorAll(".accordion-item").forEach(item => {
                    item.classList.remove("active");
                });
                
                if (!isActive) {
                    accordionItem.classList.add("active");
                }
            });
            
            accordionContainer.appendChild(accordionItem);
        }
    }

    // ----------------------------------------------------------------------
    // History Persistence in localStorage
    // ----------------------------------------------------------------------
    function getHistory() {
        try {
            return JSON.parse(localStorage.getItem("units_history") || "[]");
        } catch (e) {
            return [];
        }
    }

    function saveToHistory(expr, targetU, resultStr) {
        const history = getHistory();
        
        // Remove identical calculation to prevent duplicates
        const filtered = history.filter(item => !(item.expression === expr && item.target_unit === targetU));
        
        // Prepend new computation (maximum 15 history items cached)
        filtered.unshift({
            expression: expr,
            target_unit: targetU,
            result: resultStr,
            timestamp: Date.now()
        });
        
        if (filtered.length > 15) {
            filtered.pop();
        }
        
        localStorage.setItem("units_history", JSON.stringify(filtered));
        renderHistory();
    }

    function renderHistory() {
        const history = getHistory();
        historyContainer.innerHTML = "";
        
        if (history.length === 0) {
            historyContainer.innerHTML = `
                <div class="history-empty">No calculations recorded yet. Run a dimensionally sound expression to populate.</div>
            `;
            return;
        }

        history.forEach(item => {
            const card = document.createElement("div");
            card.className = "history-card";
            
            // Parse result approx display for history preview card
            let cleanRes = item.result;
            const approxMatch = item.result.match(/\(approx\.\s+([^)]+)\)/);
            if (approxMatch) {
                cleanRes = approxMatch[1];
            }

            card.innerHTML = `
                <div class="hist-expr" title="${item.expression}">${item.expression}</div>
                <div class="hist-target-u">To: ${item.target_unit}</div>
                <div class="hist-res" title="${item.result}">${cleanRes}</div>
            `;
            
            card.addEventListener("click", () => {
                expressionInput.value = item.expression;
                targetUnitInput.value = item.target_unit;
                
                // Trigger form submission
                solverForm.dispatchEvent(new Event("submit", { cancelable: true }));
            });
            
            historyContainer.appendChild(card);
        });
    }

    clearHistoryBtn.addEventListener("click", () => {
        localStorage.removeItem("units_history");
        renderHistory();
    });

    // ----------------------------------------------------------------------
    // API Computation Submission
    // ----------------------------------------------------------------------
    solverForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const expression = expressionInput.value.trim();
        const targetUnit = targetUnitInput.value.trim();
        
        if (!expression || !targetUnit) return;

        // Toggle Loading State
        submitBtn.disabled = true;
        submitSpinner.classList.remove("hidden");
        
        // Smoothly hide result panels
        emptyState.classList.add("hidden");
        successCard.classList.add("hidden");
        errorCard.classList.add("hidden");

        try {
            const res = await fetch("/api/compute", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    expression: expression,
                    target_unit: targetUnit
                })
            });
            
            const data = await res.json();
            
            if (res.ok && data.success) {
                handleSuccessResponse(expression, targetUnit, data.result, data.preprocessed);
            } else {
                handleErrorResponse(data.error || "Unknown server error occured.");
            }
        } catch (err) {
            handleErrorResponse(`Network connection lost: ${err.message}`);
        } finally {
            submitBtn.disabled = false;
            submitSpinner.classList.add("hidden");
        }
    });

    // ----------------------------------------------------------------------
    // Response Formatting Handlers
    // ----------------------------------------------------------------------
    function handleSuccessResponse(expr, targetU, rawResult, preprocessed) {
        successCard.classList.remove("hidden");
        
        // Format of response: "{exact_value} {unit} (approx. {approx_value} {unit})"
        // Let's parse exact, approx, and unit name
        let exactVal = rawResult;
        let approxVal = rawResult;
        let finalUnit = targetU;

        // Regex parsing approx string
        const approxRegex = /^(.*?)\s+(approx\.\s+([0-9.eE+-]+)\s+(.+))$/;
        // Or cleaner regex: matches exact value up until " (approx. {float} {unit})"
        const parsedMatch = rawResult.match(/^(.*?)\s+\(approx\.\s+([0-9.eE+-]+)\s+(.+)\)$/);
        
        if (parsedMatch) {
            exactVal = parsedMatch[1].trim();
            approxVal = parsedMatch[2].trim();
            finalUnit = parsedMatch[3].trim();
        } else {
            // In case of non-approx results, extract the unit at the end if present
            const spaceIdx = rawResult.lastIndexOf(" ");
            if (spaceIdx > 0) {
                exactVal = rawResult.substring(0, spaceIdx).trim();
                approxVal = exactVal;
                finalUnit = rawResult.substring(spaceIdx + 1).trim();
            }
        }

        // Format scientific values or long float sequences cleanly
        let displayApprox = approxVal;
        const numVal = parseFloat(approxVal);
        if (!isNaN(numVal) && (Math.abs(numVal) >= 1e6 || Math.abs(numVal) < 1e-4) && numVal !== 0) {
            displayApprox = numVal.toExponential(4);
        } else if (!isNaN(numVal)) {
            // Limit decimal places to max 6 if it's float
            if (approxVal.includes(".")) {
                displayApprox = parseFloat(numVal.toFixed(6)).toString();
            }
        }

        // Update success card view
        answerApprox.textContent = displayApprox;
        answerUnit.textContent = finalUnit;
        metricExact.textContent = exactVal;
        metricDim.textContent = inferDimensionality(finalUnit);
        
        // Approximate internal value in base SI units
        const scaleFactor = getEstimatedScale(finalUnit);
        const internalVal = !isNaN(numVal) ? (numVal * scaleFactor) : "N/A";
        metricInternal.textContent = typeof internalVal === "number" ? 
            (internalVal.toString().includes(".") ? parseFloat(internalVal.toFixed(6)).toString() : internalVal) 
            : internalVal;

        // Dynamically inject step details for the timeline
        const showPreprocessed = preprocessed || expr;
        stepToken.innerHTML = `Messy natural input successfully preprocessed inside the AST sandbox to: <code class="font-code" style="color: var(--accent); font-size: 0.85rem;">${showPreprocessed}</code>.`;
        stepCoord.innerHTML = `Calculation resolved using SymPy exact Rational arithmetic. Absolute temperature constraints coordinate check passed. Exact value computed as: <code class="font-code" style="color: var(--primary)">${exactVal}</code>.`;
        stepScale.textContent = `Applied target unit scale mapping and verified physical dimension consistency. Successfully converted to '${targetU}'.`;

        // Save to browser history
        saveToHistory(expr, targetU, rawResult);
    }

    function handleErrorResponse(errStr) {
        errorCard.classList.remove("hidden");
        
        let category = "Evaluation Error";
        let message = errStr;
        let tips = [];

        // Parse category prefix returned by the Python server
        const categories = ["Security Error", "Parsing Error", "Type Error", "Math Error"];
        for (const cat of categories) {
            if (errStr.startsWith(cat + ":")) {
                category = cat;
                message = errStr.substring(cat.length + 1).trim();
                break;
            }
        }

        errorCategory.textContent = category;
        errorMessage.textContent = message;

        // Populate helpful dynamic tips based on error category
        if (category === "Security Error") {
            tips = [
                "The AST sandbox prevents security execution of arbitrary Python functions.",
                "Make sure you are not calling any functions (like 'sin()', 'cos()', or '__import__').",
                "Only standard numbers, variable unit names, and whitelisted operators (+, -, *, /, **) are allowed."
            ];
        } else if (category === "Parsing Error") {
            tips = [
                "Verify that all parenthesis, brackets, and arithmetic operators are properly balanced.",
                "Ensure that all symbol names you typed are valid physical units (check the Palette below).",
                "Ensure you did not use bitwise operators (like &, |) which are unauthorized in this sandbox."
            ];
        } else if (category === "Type Error") {
            tips = [
                "Check for dimensional consistency: you cannot add or subtract different dimensions (e.g. '10 m + 5 kg').",
                "Check temperature arithmetic: absolute coordinates (degC, degF) cannot be added together or scaled.",
                "To adjust temperatures coordinates, subtract them to get a delta difference, or add a delta shift unit (e.g. '10 delta_degC').",
                "Exponents must be purely dimensionless numbers or units (e.g. '10 m ** 2', but not '10 m ** (2 s)')."
            ];
        } else if (category === "Math Error") {
            tips = [
                "Mathematical error detected: make sure you are not dividing any quantity by zero (e.g. '10 m / 0').",
                "Check that you are not raising a zero value to a negative exponent (which implies division by zero)."
            ];
        } else {
            tips = [
                "Verify that your expression and target unit are correct.",
                "Check that you did not introduce spelling typos in unit names."
            ];
        }

        errorTipsList.innerHTML = "";
        tips.forEach(tip => {
            const li = document.createElement("li");
            li.textContent = tip;
            errorTipsList.appendChild(li);
        });
    }

    // ----------------------------------------------------------------------
    // Physical Dimension Inference & Estimator Engine
    // ----------------------------------------------------------------------
    function inferDimensionality(unitStr) {
        // Fallback helper to visually show dimensionality when pint is not client-side
        const match = unitStr.toLowerCase();
        
        if (match.includes("meter") || match.includes("foot") || match.includes("inch") || match.includes("mile") || match.includes("yard") || match === "m" || match === "ft" || match === "in" || match === "mi") {
            return "[length]";
        }
        if (match.includes("second") || match.includes("minute") || match.includes("hour") || match.includes("day") || match === "s" || match === "min" || match === "hr" || match === "h") {
            return "[time]";
        }
        if (match.includes("gram") || match.includes("pound") || match.includes("ounce") || match === "g" || match === "kg" || match === "lb" || match === "oz") {
            return "[mass]";
        }
        if (match.includes("celsius") || match.includes("fahrenheit") || match.includes("kelvin") || match.includes("rankine") || match.includes("deg") || match === "k" || match === "r") {
            return "[temperature]";
        }
        if (match.includes("/") && (match.includes("second") || match.includes("s")) && (match.includes("meter") || match.includes("m") || match.includes("mile"))) {
            if (match.includes("**2") || match.includes("s**2") || match.includes("s^2")) {
                return "[length] * [time] ** -2";
            }
            return "[length] * [time] ** -1";
        }
        if (match.includes("newton") || match.includes("lbf") || match === "n") {
            return "[mass] * [length] * [time] ** -2";
        }
        if (match.includes("pascal") || match.includes("bar") || match.includes("psi") || match === "pa") {
            return "[mass] * [length] ** -1 * [time] ** -2";
        }
        if (match.includes("joule") || match.includes("calorie") || match === "j" || match === "cal") {
            return "[mass] * [length] ** 2 * [time] ** -2";
        }
        if (match.includes("watt") || match === "w" || match === "kw") {
            return "[mass] * [length] ** 2 * [time] ** -3";
        }
        if (match.includes("dimensionless") || match.includes("%") || match.includes("degree") || match.includes("rad")) {
            return "dimensionless";
        }
        return "[derived dimension]";
    }

    function getEstimatedScale(unitStr) {
        // Estimated scale factors in SI base units (m, kg, s, K) for display aesthetics
        const match = unitStr.toLowerCase();
        
        if (match === "m" || match.includes("meter")) return 1;
        if (match === "cm" || match.includes("centimeter")) return 0.01;
        if (match === "mm" || match.includes("millimeter")) return 0.001;
        if (match === "km" || match.includes("kilometer")) return 1000;
        if (match === "in" || match.includes("inch")) return 0.0254;
        if (match === "ft" || match.includes("foot")) return 0.3048;
        if (match === "yd" || match.includes("yard")) return 0.9144;
        if (match === "mi" || match.includes("mile")) return 1609.344;
        
        if (match === "kg" || match.includes("kilogram")) return 1;
        if (match === "g" || match.includes("gram")) return 0.001;
        if (match === "lb" || match.includes("pound")) return 0.45359237;
        
        if (match === "s" || match.includes("second")) return 1;
        if (match === "min" || match.includes("minute")) return 60;
        if (match === "hr" || match.includes("hour")) return 3600;
        
        return 1; // Default fallback scale
    }

    // ----------------------------------------------------------------------
    // SHOWCASE RECIPES DATA & BUILDER ENGINE
    // ----------------------------------------------------------------------
    const presetRecipes = [
        {
            name: "Kinematics (Implicit Mult)",
            expression: "10 m/s * 5 s",
            target: "ft",
            capability: "Implicit mult & derived conversion"
        },
        {
            name: "Energy (Rational Identity)",
            expression: "500 W * 2 hr",
            target: "MJ",
            capability: "Exact rational precision"
        },
        {
            name: "Fuel Reciprocals",
            expression: "30 mpg",
            target: "l/100km",
            capability: "Generalized reciprocal inversion"
        },
        {
            name: "Temp Coordinates",
            expression: "20 degC + 5 delta_degC",
            target: "degC",
            capability: "Affine temperature offset shift"
        },
        {
            name: "Temp Safety Guard",
            expression: "30 degC + 10 degC",
            target: "degC",
            capability: "Coordinate addition safety guard"
        },
        {
            name: "Unicode Geometry",
            expression: "2 * π * 10 cm",
            target: "m",
            capability: "Unicode symbol & constants mapping"
        },
        {
            name: "Percentage Scaling",
            expression: "100 m * 5%",
            target: "m",
            capability: "Percentage ratio normalization"
        },
        {
            name: "Fluid Dynamics (Reynolds)",
            expression: "(1000 kg / m**3 * 2 m/s * 0.1 m) / (1e-3 Pa * s)",
            target: "dimensionless",
            capability: "Derived dimensionless Reynolds number"
        },
        {
            name: "Molar Chemistry",
            expression: "5 mol + 2000 mmol",
            target: "mol",
            capability: "Substance amount & metric prefix shift"
        },
        {
            name: "RCE Exploit Blocker",
            expression: "__import__('os').system('ls')",
            target: "m",
            capability: "Strict AST sandbox whitelist"
        }
    ];

    function buildPresetRecipes() {
        const container = document.getElementById("preset-recipes-container");
        if (!container) return;
        
        container.innerHTML = "";
        
        presetRecipes.forEach(recipe => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "preset-chip-btn";
            btn.textContent = recipe.name;
            btn.title = `Showcases: ${recipe.capability}\nFormula: ${recipe.expression} -> ${recipe.target}`;
            
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                expressionInput.value = recipe.expression;
                targetUnitInput.value = recipe.target;
                
                // Track last focused input
                lastFocusedInput = expressionInput;
                
                // Smooth focus effect
                expressionInput.focus();
                
                // Auto execute calculation
                solverForm.dispatchEvent(new Event("submit"));
            });
            
            container.appendChild(btn);
        });
    }

    // ----------------------------------------------------------------------
    // AGENT PROMPT SANDBOX SCENARIOS & ENGINE
    // ----------------------------------------------------------------------
    const promptScenarios = {
        kinematics: `Discrepancy Report:
The drone velocity was measured at 10 m/s for a duration of 5 s.
The telemetry claims a final displacement of 160 ft.
Verify if this claim is dimensionally and algebraically correct compared to actual math.`,

        energy: `Generator Log:
The auxiliary backup generator ran at 500 W for exactly 2 hr.
The primary log records a total consumption of 3.6 MJ.
Verify if the exact rational math matches the logged energy value.`,

        reactor: `Reactor Telemetry Alert:
The main coolant temperature was measured at 30 degC.
The control room operator attempted to shift the absolute temperature by adding 10 degC to represent the increase.
The operator recorded the final state as 40 degC.
Verify if this operation is physically valid or if it violates coordinate temperature constraints.`
    };

    const sandboxTextarea = document.getElementById("sandbox-textarea");
    const promptPreview = document.getElementById("prompt-preview");
    const copyPromptBtn = document.getElementById("copy-prompt-btn");
    const scenarioTabBtns = document.querySelectorAll(".sandbox-tabs .tab-btn");

    function generatePromptTemplate(text) {
        return `You are an expert physics and engineering validator. Your task is to analyze the following technical document, extract all implicit and explicit physical formulas or mathematical claims, and verify their dimensional and algebraic correctness.

For every physical equation or conversion claim in the text:
1. Extract the algebraic expression and its claimed result unit.
2. Sequentially call the \`dimensional_compute\` tool to evaluate the expression and convert it to the claimed result unit.
3. Verify if the computed value and unit match the document's claim.
4. Compile a formal validation report. For any discrepancies, explain the physical error (e.g. incorrect scaling factor, adding absolute coordinates, or mismatched dimensions).

Here is the document to analyze:
---
${text.trim()}
---`;
    }

    function updatePromptPreview() {
        if (!sandboxTextarea || !promptPreview) return;
        const text = sandboxTextarea.value;
        promptPreview.textContent = generatePromptTemplate(text);
    }

    function initPromptSandbox() {
        if (!sandboxTextarea) return;

        let activeScenario = "kinematics";

        // DOM elements for prompt sandbox refactor
        const togglePromptBtn = document.getElementById("toggle-prompt-btn");
        const promptContainer = document.getElementById("prompt-container");
        const runPipelineBtn = document.getElementById("run-pipeline-btn");
        const pipelineSpinner = runPipelineBtn ? runPipelineBtn.querySelector(".pipeline-spinner") : null;
        const agentConsoleCard = document.getElementById("agent-console-card");
        const consoleLogsContainer = document.getElementById("console-logs-container");
        const formalReportContainer = document.getElementById("formal-report-container");
        const agentStatusBadge = document.getElementById("agent-status-badge");

        // Set default scenario
        sandboxTextarea.value = promptScenarios.kinematics;
        updatePromptPreview();

        // Listen for live textarea typing/edits
        sandboxTextarea.addEventListener("input", updatePromptPreview);

        // Segmented Tabs click handling
        scenarioTabBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                scenarioTabBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                
                const scenarioKey = btn.getAttribute("data-scenario");
                if (promptScenarios[scenarioKey]) {
                    sandboxTextarea.value = promptScenarios[scenarioKey];
                    updatePromptPreview();
                    activeScenario = scenarioKey;
                }
            });
        });

        // Collapsible prompt inspection toggle
        if (togglePromptBtn && promptContainer) {
            togglePromptBtn.addEventListener("click", () => {
                const isHidden = promptContainer.classList.contains("hidden");
                if (isHidden) {
                    promptContainer.classList.remove("hidden");
                    togglePromptBtn.classList.add("active");
                } else {
                    promptContainer.classList.add("hidden");
                    togglePromptBtn.classList.remove("active");
                }
            });
        }

        // Copy button handling
        if (copyPromptBtn) {
            copyPromptBtn.addEventListener("click", async () => {
                const promptText = promptPreview.textContent;
                try {
                    await navigator.clipboard.writeText(promptText);
                    
                    // Copy micro-animation transition
                    copyPromptBtn.classList.add("copied");
                    const originalText = copyPromptBtn.querySelector("span").textContent;
                    copyPromptBtn.querySelector("span").textContent = "Copied!";
                    
                    setTimeout(() => {
                        copyPromptBtn.classList.remove("copied");
                        copyPromptBtn.querySelector("span").textContent = originalText;
                    }, 2000);
                } catch (err) {
                    alert("Failed to copy prompt to clipboard. Please copy manually.");
                }
            });
        }

        // --- Simulated Typewriter Logs & Markdown rendering engine ---
        function appendConsoleLog(action, log, stepNum, categoryClass) {
            if (!consoleLogsContainer) return;
            const line = document.createElement("div");
            line.className = `console-log-line ${categoryClass || ''}`;
            const now = new Date();
            const timeStr = now.toTimeString().split(" ")[0];
            line.innerHTML = `
                <span class="console-time">[${timeStr}]</span>
                <span class="console-text"><strong>[Step ${stepNum}] ${action}:</strong> ${log}</span>
            `;
            consoleLogsContainer.appendChild(line);
            consoleLogsContainer.scrollTop = consoleLogsContainer.scrollHeight;
        }

        function updateBadgeState(status) {
            if (!agentStatusBadge) return;
            agentStatusBadge.className = "badge";
            if (status === "verified") {
                agentStatusBadge.textContent = "Fully Verified";
                agentStatusBadge.classList.add("badge-success");
            } else if (status === "discrepancy") {
                agentStatusBadge.textContent = "Discrepancy Detected";
                agentStatusBadge.classList.add("badge-warning");
            } else if (status === "violation") {
                agentStatusBadge.textContent = "Violation Blocked";
                agentStatusBadge.classList.add("badge-danger");
            } else if (status === "error") {
                agentStatusBadge.textContent = "Execution Failed";
                agentStatusBadge.classList.add("badge-danger");
            } else {
                agentStatusBadge.textContent = status;
                agentStatusBadge.classList.add("badge-primary");
            }
        }

        function renderMarkdownToHtml(md) {
            if (!md) return "";
            let html = md
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
            html = html.replace(/^###\s+(.*?)$/gm, '<h3>$1</h3>');
            html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/`(.*?)`/g, '<code>$1</code>');
            
            const lines = html.split('\n');
            let inList = false;
            const processedLines = lines.map(line => {
                const trimmed = line.trim();
                if (trimmed.startsWith('- ')) {
                    const content = trimmed.substring(2);
                    let res = '';
                    if (!inList) {
                        inList = true;
                        res += '<ul>';
                    }
                    res += `<li>${content}</li>`;
                    return res;
                } else {
                    let res = '';
                    if (inList) {
                        inList = false;
                        res += '</ul>';
                    }
                    res += line;
                    return res;
                }
            });
            if (inList) {
                processedLines.push('</ul>');
            }
            html = processedLines.join('\n');
            html = html.replace(/\n\n/g, '<p></p>');
            return html;
        }

        function handlePipelineError(errMsg) {
            appendConsoleLog("Connection Failure", `Failed to reach backend verification agent: ${errMsg}`, "X", "error-log");
            updateBadgeState("error");
            if (formalReportContainer) {
                formalReportContainer.innerHTML = `
                    <div style="color: var(--danger); font-size: 0.9rem; padding: 0.5rem 0;">
                        <strong>Error:</strong> The AI Agent Pipeline encountered a communication error.
                        Please ensure the local Skookum companion server is running and try again.
                    </div>
                `;
            }
            if (runPipelineBtn) runPipelineBtn.disabled = false;
            if (pipelineSpinner) pipelineSpinner.classList.add("hidden");
        }

        if (runPipelineBtn) {
            runPipelineBtn.addEventListener("click", async () => {
                runPipelineBtn.disabled = true;
                if (pipelineSpinner) pipelineSpinner.classList.remove("hidden");
                if (agentConsoleCard) agentConsoleCard.classList.remove("hidden");
                if (consoleLogsContainer) consoleLogsContainer.innerHTML = "";
                if (formalReportContainer) formalReportContainer.innerHTML = "";
                
                updateBadgeState("Analyzing...");
                appendConsoleLog("Initialize", "Waking up headless verification agent pipeline...", 0, "nlp");

                try {
                    const response = await fetch("/api/verify", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            scenario: activeScenario,
                            text: sandboxTextarea.value
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.success && data.report) {
                        const report = data.report;
                        const steps = report.steps || [];
                        
                        steps.forEach((step, i) => {
                            setTimeout(() => {
                                let catClass = "";
                                const lowerAct = step.action.toLowerCase();
                                if (lowerAct.includes("nlp") || lowerAct.includes("scan") || lowerAct.includes("extract")) {
                                    catClass = "nlp";
                                } else if (lowerAct.includes("mcp") || lowerAct.includes("tool") || lowerAct.includes("solver") || lowerAct.includes("execute")) {
                                    catClass = "tool";
                                } else if (lowerAct.includes("block") || lowerAct.includes("violation") || lowerAct.includes("intercept") || lowerAct.includes("error") || lowerAct.includes("failed")) {
                                    catClass = "error-log";
                                }
                                
                                appendConsoleLog(step.action, step.log, step.step, catClass);
                                
                                if (agentStatusBadge) {
                                    agentStatusBadge.textContent = `Running: ${step.action}...`;
                                }
                                
                                if (i === steps.length - 1) {
                                    setTimeout(() => {
                                        updateBadgeState(report.status);
                                        appendConsoleLog("Pipeline Complete", "Formal safety and dimensional audit report compiled successfully.", steps.length + 1, report.status === "verified" ? "nlp" : (report.status === "discrepancy" ? "tool" : "error-log"));
                                        if (formalReportContainer) {
                                            formalReportContainer.innerHTML = renderMarkdownToHtml(report.report);
                                        }
                                        runPipelineBtn.disabled = false;
                                        if (pipelineSpinner) pipelineSpinner.classList.add("hidden");
                                    }, 400);
                                }
                            }, (i + 1) * 400); // 400ms delay per step
                        });
                    } else {
                        const err = data.error || "Unknown server validation error.";
                        handlePipelineError(err);
                    }
                } catch (e) {
                    handlePipelineError(e.message);
                }
            });
        }
    }

    // ----------------------------------------------------------------------
    // Initialization Boots
    // ----------------------------------------------------------------------
    fetchSupportedUnits();
    renderHistory();
    buildPresetRecipes();
    initPromptSandbox();
});
