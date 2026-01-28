#!/usr/bin/env python3
"""
Seed Software Lab Templates
Start with 1 simple template: Calculator
"""

from src.database.db_manager import DBManager
from datetime import datetime
from uuid import uuid4


def seed_calculator_template():
    """Seed Calculator template (Web - Beginner)"""

    db_manager = DBManager()
    db = db_manager.db

    print("📦 Seeding Calculator Template...")

    # Template metadata
    template = {
        "id": "calculator",
        "name": "Calculator App",
        "description": "Build a simple calculator with HTML, CSS, and JavaScript. Learn DOM manipulation and basic arithmetic operations.",
        "category": "web",
        "difficulty": "beginner",
        "thumbnail_url": "https://via.placeholder.com/400x300/4CAF50/ffffff?text=Calculator",
        "tags": ["html", "css", "javascript", "beginner", "dom"],
        "file_count": 3,
        "estimated_time_minutes": 60,
        "guide_steps": [
            {
                "step": 1,
                "title": "Create HTML Structure",
                "description": "Build the calculator layout with buttons for digits 0-9 and operators (+, -, *, /, =)",
                "files_to_edit": ["index.html"],
            },
            {
                "step": 2,
                "title": "Style with CSS",
                "description": "Make the calculator look good with grid layout and button styling",
                "files_to_edit": ["styles.css"],
            },
            {
                "step": 3,
                "title": "Add JavaScript Logic",
                "description": "Implement calculator functions: handleClick, calculate, clear, backspace",
                "files_to_edit": ["app.js"],
            },
            {
                "step": 4,
                "title": "Test Your Calculator",
                "description": "Try different calculations: 5 + 3, 10 * 2, 15 / 3",
                "files_to_edit": [],
            },
        ],
        "is_active": True,
        "created_at": datetime.utcnow(),
    }

    # Check if template already exists
    existing = db.software_lab_templates.find_one({"id": "calculator"})
    if existing:
        print("   ⚠️  Calculator template already exists, updating...")
        db.software_lab_templates.update_one({"id": "calculator"}, {"$set": template})
    else:
        db.software_lab_templates.insert_one(template)
        print("   ✅ Calculator template created")

    # Template files
    files = [
        {
            "id": f"template_file_{uuid4().hex[:12]}",
            "template_id": "calculator",
            "path": "index.html",
            "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Calculator</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="calculator">
        <div class="display">
            <div class="previous-operand"></div>
            <div class="current-operand">0</div>
        </div>

        <button class="span-2" onclick="calculator.clear()">AC</button>
        <button onclick="calculator.backspace()">DEL</button>
        <button class="operator" onclick="calculator.chooseOperation('÷')">÷</button>

        <button onclick="calculator.appendNumber('7')">7</button>
        <button onclick="calculator.appendNumber('8')">8</button>
        <button onclick="calculator.appendNumber('9')">9</button>
        <button class="operator" onclick="calculator.chooseOperation('×')">×</button>

        <button onclick="calculator.appendNumber('4')">4</button>
        <button onclick="calculator.appendNumber('5')">5</button>
        <button onclick="calculator.appendNumber('6')">6</button>
        <button class="operator" onclick="calculator.chooseOperation('-')">-</button>

        <button onclick="calculator.appendNumber('1')">1</button>
        <button onclick="calculator.appendNumber('2')">2</button>
        <button onclick="calculator.appendNumber('3')">3</button>
        <button class="operator" onclick="calculator.chooseOperation('+')">+</button>

        <button onclick="calculator.appendNumber('0')">0</button>
        <button onclick="calculator.appendNumber('.')">.</button>
        <button class="span-2 equal" onclick="calculator.calculate()">=</button>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            "language": "html",
            "is_editable": True,
        },
        {
            "id": f"template_file_{uuid4().hex[:12]}",
            "template_id": "calculator",
            "path": "styles.css",
            "content": """* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.calculator {
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    padding: 20px;
    width: 400px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}

.display {
    grid-column: 1 / -1;
    background: #222;
    color: white;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 10px;
    text-align: right;
}

.previous-operand {
    color: rgba(255, 255, 255, 0.5);
    font-size: 1.2rem;
    min-height: 1.5rem;
}

.current-operand {
    font-size: 2.5rem;
    font-weight: bold;
    min-height: 3rem;
}

button {
    background: #f0f0f0;
    border: none;
    border-radius: 10px;
    font-size: 1.5rem;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s;
}

button:hover {
    background: #e0e0e0;
    transform: scale(1.05);
}

button:active {
    transform: scale(0.95);
}

.span-2 {
    grid-column: span 2;
}

.operator {
    background: #ff9500;
    color: white;
}

.operator:hover {
    background: #e68600;
}

.equal {
    background: #4CAF50;
    color: white;
}

.equal:hover {
    background: #45a049;
}""",
            "language": "css",
            "is_editable": True,
        },
        {
            "id": f"template_file_{uuid4().hex[:12]}",
            "template_id": "calculator",
            "path": "app.js",
            "content": """class Calculator {
    constructor(previousOperandElement, currentOperandElement) {
        this.previousOperandElement = previousOperandElement;
        this.currentOperandElement = currentOperandElement;
        this.clear();
    }

    clear() {
        this.currentOperand = '0';
        this.previousOperand = '';
        this.operation = undefined;
    }

    backspace() {
        if (this.currentOperand === '0') return;
        this.currentOperand = this.currentOperand.toString().slice(0, -1);
        if (this.currentOperand === '') this.currentOperand = '0';
    }

    appendNumber(number) {
        if (number === '.' && this.currentOperand.includes('.')) return;
        if (this.currentOperand === '0' && number !== '.') {
            this.currentOperand = number.toString();
        } else {
            this.currentOperand = this.currentOperand.toString() + number.toString();
        }
    }

    chooseOperation(operation) {
        if (this.currentOperand === '') return;
        if (this.previousOperand !== '') {
            this.calculate();
        }
        this.operation = operation;
        this.previousOperand = this.currentOperand;
        this.currentOperand = '0';
    }

    calculate() {
        let computation;
        const prev = parseFloat(this.previousOperand);
        const current = parseFloat(this.currentOperand);

        if (isNaN(prev) || isNaN(current)) return;

        switch (this.operation) {
            case '+':
                computation = prev + current;
                break;
            case '-':
                computation = prev - current;
                break;
            case '×':
                computation = prev * current;
                break;
            case '÷':
                if (current === 0) {
                    alert('Cannot divide by zero!');
                    return;
                }
                computation = prev / current;
                break;
            default:
                return;
        }

        this.currentOperand = computation.toString();
        this.operation = undefined;
        this.previousOperand = '';
    }

    updateDisplay() {
        this.currentOperandElement.innerText = this.currentOperand;
        if (this.operation != null) {
            this.previousOperandElement.innerText =
                `${this.previousOperand} ${this.operation}`;
        } else {
            this.previousOperandElement.innerText = '';
        }
    }
}

// Initialize calculator
const previousOperandElement = document.querySelector('.previous-operand');
const currentOperandElement = document.querySelector('.current-operand');

const calculator = new Calculator(previousOperandElement, currentOperandElement);

// Update display after each operation
setInterval(() => {
    calculator.updateDisplay();
}, 100);

console.log('✅ Calculator loaded successfully!');
console.log('Try: 5 + 3, 10 × 2, 15 ÷ 3');""",
            "language": "javascript",
            "is_editable": True,
        },
    ]

    # Delete old template files if exists
    db.software_lab_template_files.delete_many({"template_id": "calculator"})

    # Insert template files
    db.software_lab_template_files.insert_many(files)
    print(f"   ✅ {len(files)} template files created")

    print("\n✅ Calculator template seeded successfully!")
    print("\n📝 Template Details:")
    print(f"   ID: {template['id']}")
    print(f"   Name: {template['name']}")
    print(f"   Category: {template['category']}")
    print(f"   Difficulty: {template['difficulty']}")
    print(f"   Files: {len(files)}")
    print(f"   Estimated Time: {template['estimated_time_minutes']} minutes")


if __name__ == "__main__":
    seed_calculator_template()
