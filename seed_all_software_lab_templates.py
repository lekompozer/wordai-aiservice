"""
Seed all 9 Software Lab templates with their files
Run: python seed_all_software_lab_templates.py
"""

from src.database.db_manager import DBManager
from datetime import datetime
import secrets

db_manager = DBManager()
db = db_manager.db


def seed_all_templates():
    """Seed all 9 Software Lab templates"""

    # Clear existing templates and files to avoid conflicts
    print("Clearing existing templates and files...")
    db.software_lab_templates.delete_many({})
    db.software_lab_template_files.delete_many({})
    print("✅ Cleared existing data\n")

    templates = [
        # ========== MOBILE APPS ==========
        {
            "id": "calculator_app",
            "name": "Calculator App",
            "description": "A simple calculator application for basic arithmetic operations",
            "category": "mobile",
            "difficulty": "beginner",
            "language": "javascript",
            "estimated_time_minutes": 60,
            "thumbnail_url": None,
            "guide_steps": [
                "Set up the basic HTML structure with number buttons and operators",
                "Style the calculator with CSS Grid for a clean layout",
                "Implement the Calculator class for operations",
                "Add event listeners and connect UI to logic",
            ],
            "tags": ["mobile", "calculator", "beginner", "javascript"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "todo_app",
            "name": "Todo List App",
            "description": "A task management app with add, complete, and delete functionality",
            "category": "mobile",
            "difficulty": "beginner",
            "language": "javascript",
            "estimated_time_minutes": 90,
            "thumbnail_url": None,
            "guide_steps": [
                "Create the UI with input field and task list container",
                "Implement task creation and rendering",
                "Add complete/uncomplete toggle functionality",
                "Implement task deletion with localStorage persistence",
            ],
            "tags": ["mobile", "todo", "beginner", "javascript", "localStorage"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "expense_tracker",
            "name": "Expense Tracker",
            "description": "Track your income and expenses with visual charts",
            "category": "mobile",
            "difficulty": "intermediate",
            "language": "javascript",
            "estimated_time_minutes": 120,
            "thumbnail_url": None,
            "guide_steps": [
                "Design the transaction form with income/expense toggle",
                "Build the transaction list with category filters",
                "Calculate and display total balance",
                "Add simple bar chart visualization",
                "Implement localStorage for data persistence",
            ],
            "tags": ["mobile", "finance", "intermediate", "javascript", "charts"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        # ========== WEBSITES ==========
        {
            "id": "student_management",
            "name": "Student Management System",
            "description": "A CRUD system to manage student records with search and filter",
            "category": "web",
            "difficulty": "intermediate",
            "language": "javascript",
            "estimated_time_minutes": 150,
            "thumbnail_url": None,
            "guide_steps": [
                "Create student form with validation (name, ID, grade, major)",
                "Build student table with edit/delete actions",
                "Implement search by name or student ID",
                "Add filter by grade level",
                "Use localStorage to persist student data",
            ],
            "tags": ["web", "crud", "intermediate", "javascript", "forms"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "landing_page",
            "name": "Modern Landing Page",
            "description": "A responsive landing page with hero section, features, and contact form",
            "category": "web",
            "difficulty": "beginner",
            "language": "html",
            "estimated_time_minutes": 90,
            "thumbnail_url": None,
            "guide_steps": [
                "Build HTML structure with semantic tags (header, main, footer)",
                "Create hero section with call-to-action button",
                "Design features section with icon cards",
                "Style with modern CSS (flexbox, gradients, shadows)",
                "Make it responsive with media queries",
            ],
            "tags": ["web", "landing", "beginner", "html", "css", "responsive"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "personal_blog",
            "name": "Personal Blog",
            "description": "A blog website with posts, comments, and categories",
            "category": "web",
            "difficulty": "intermediate",
            "language": "javascript",
            "estimated_time_minutes": 180,
            "thumbnail_url": None,
            "guide_steps": [
                "Create blog post structure (title, content, author, date)",
                "Build post list with category filters",
                "Implement post detail page with comments",
                "Add comment form and display",
                "Use localStorage for posts and comments data",
            ],
            "tags": ["web", "blog", "intermediate", "javascript", "content"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        # ========== GAMES ==========
        {
            "id": "snake_game",
            "name": "Snake Game",
            "description": "Classic snake game with keyboard controls and score tracking",
            "category": "game",
            "difficulty": "intermediate",
            "language": "javascript",
            "estimated_time_minutes": 120,
            "thumbnail_url": None,
            "guide_steps": [
                "Set up canvas and grid system",
                "Implement snake movement with arrow keys",
                "Add food spawning and collision detection",
                "Implement score tracking and game over logic",
                "Add restart functionality",
            ],
            "tags": ["game", "snake", "intermediate", "javascript", "canvas"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "flappy_bird",
            "name": "Flappy Bird Clone",
            "description": "Tap to flap and avoid obstacles in this addictive game",
            "category": "game",
            "difficulty": "advanced",
            "language": "javascript",
            "estimated_time_minutes": 180,
            "thumbnail_url": None,
            "guide_steps": [
                "Create canvas game loop with requestAnimationFrame",
                "Implement bird physics (gravity, jump)",
                "Generate moving pipe obstacles",
                "Detect collisions with pipes and boundaries",
                "Add score system and game state management",
            ],
            "tags": ["game", "flappy", "advanced", "javascript", "physics"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": "memory_card",
            "name": "Memory Card Game",
            "description": "Match pairs of cards to win in this memory challenge game",
            "category": "game",
            "difficulty": "beginner",
            "language": "javascript",
            "estimated_time_minutes": 90,
            "thumbnail_url": None,
            "guide_steps": [
                "Create card grid with HTML/CSS",
                "Implement card flip animation",
                "Add matching logic for card pairs",
                "Track moves and matched pairs",
                "Add win condition and reset button",
            ],
            "tags": ["game", "memory", "beginner", "javascript", "cards"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    ]

    # Template files for each template
    template_files = {
        "calculator_app": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Calculator App</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="calculator">
        <div class="display" id="display">0</div>
        <div class="buttons">
            <button class="btn" onclick="clearDisplay()">C</button>
            <button class="btn" onclick="deleteLast()">←</button>
            <button class="btn operator" onclick="appendOperator('/')">÷</button>
            <button class="btn operator" onclick="appendOperator('*')">×</button>

            <button class="btn" onclick="appendNumber('7')">7</button>
            <button class="btn" onclick="appendNumber('8')">8</button>
            <button class="btn" onclick="appendNumber('9')">9</button>
            <button class="btn operator" onclick="appendOperator('-')">−</button>

            <button class="btn" onclick="appendNumber('4')">4</button>
            <button class="btn" onclick="appendNumber('5')">5</button>
            <button class="btn" onclick="appendNumber('6')">6</button>
            <button class="btn operator" onclick="appendOperator('+')">+</button>

            <button class="btn" onclick="appendNumber('1')">1</button>
            <button class="btn" onclick="appendNumber('2')">2</button>
            <button class="btn" onclick="appendNumber('3')">3</button>
            <button class="btn equals" onclick="calculate()" style="grid-row: span 2">=</button>

            <button class="btn" onclick="appendNumber('0')" style="grid-column: span 2">0</button>
            <button class="btn" onclick="appendNumber('.')">.</button>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.calculator {
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    overflow: hidden;
    width: 320px;
}

.display {
    background: #2d3748;
    color: white;
    font-size: 2.5rem;
    padding: 30px;
    text-align: right;
    min-height: 100px;
    word-wrap: break-word;
}

.buttons {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: #e2e8f0;
    padding: 1px;
}

.btn {
    border: none;
    background: white;
    font-size: 1.5rem;
    padding: 25px;
    cursor: pointer;
    transition: background 0.2s;
}

.btn:hover {
    background: #f7fafc;
}

.btn:active {
    background: #e2e8f0;
}

.operator {
    background: #fed7d7;
    color: #c53030;
}

.operator:hover {
    background: #fc8181;
    color: white;
}

.equals {
    background: #667eea;
    color: white;
}

.equals:hover {
    background: #5a67d8;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """let display = document.getElementById('display');
let currentValue = '0';
let previousValue = '';
let operation = null;
let shouldResetDisplay = false;

function updateDisplay() {
    display.textContent = currentValue;
}

function appendNumber(num) {
    if (shouldResetDisplay) {
        currentValue = num;
        shouldResetDisplay = false;
    } else {
        currentValue = currentValue === '0' ? num : currentValue + num;
    }
    updateDisplay();
}

function appendOperator(op) {
    if (operation !== null) {
        calculate();
    }
    previousValue = currentValue;
    operation = op;
    shouldResetDisplay = true;
}

function calculate() {
    if (operation === null || shouldResetDisplay) return;

    const prev = parseFloat(previousValue);
    const current = parseFloat(currentValue);
    let result;

    switch(operation) {
        case '+': result = prev + current; break;
        case '-': result = prev - current; break;
        case '*': result = prev * current; break;
        case '/': result = prev / current; break;
        default: return;
    }

    currentValue = result.toString();
    operation = null;
    shouldResetDisplay = true;
    updateDisplay();
}

function clearDisplay() {
    currentValue = '0';
    previousValue = '';
    operation = null;
    shouldResetDisplay = false;
    updateDisplay();
}

function deleteLast() {
    currentValue = currentValue.length > 1 ? currentValue.slice(0, -1) : '0';
    updateDisplay();
}""",
            },
        ],
        "todo_app": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Todo List App</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h1>📝 My Todo List</h1>

        <div class="input-section">
            <input type="text" id="taskInput" placeholder="Add a new task...">
            <button onclick="addTask()">Add Task</button>
        </div>

        <div class="filter-section">
            <button onclick="filterTasks('all')" class="active">All</button>
            <button onclick="filterTasks('active')">Active</button>
            <button onclick="filterTasks('completed')">Completed</button>
        </div>

        <ul id="taskList"></ul>

        <div class="stats">
            <span id="taskCount">0 tasks remaining</span>
            <button onclick="clearCompleted()">Clear Completed</button>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 600px;
    margin: 50px auto;
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

h1 {
    text-align: center;
    color: #2d3748;
    margin-bottom: 30px;
}

.input-section {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}

#taskInput {
    flex: 1;
    padding: 15px;
    font-size: 16px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
}

button {
    padding: 15px 25px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: background 0.3s;
}

button:hover {
    background: #5a67d8;
}

.filter-section {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}

.filter-section button {
    flex: 1;
    background: #e2e8f0;
    color: #2d3748;
}

.filter-section button.active {
    background: #667eea;
    color: white;
}

#taskList {
    list-style: none;
    margin-bottom: 20px;
}

.task-item {
    display: flex;
    align-items: center;
    padding: 15px;
    background: #f7fafc;
    margin-bottom: 10px;
    border-radius: 8px;
    transition: all 0.3s;
}

.task-item:hover {
    background: #edf2f7;
}

.task-item.completed .task-text {
    text-decoration: line-through;
    opacity: 0.5;
}

.task-text {
    flex: 1;
    margin: 0 15px;
}

.delete-btn {
    background: #fc8181;
    padding: 8px 15px;
    font-size: 14px;
}

.delete-btn:hover {
    background: #f56565;
}

.stats {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 20px;
    border-top: 2px solid #e2e8f0;
    color: #718096;
}

.stats button {
    background: #fed7d7;
    color: #c53030;
    padding: 10px 20px;
    font-size: 14px;
}

.stats button:hover {
    background: #fc8181;
    color: white;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """let tasks = JSON.parse(localStorage.getItem('tasks')) || [];
let currentFilter = 'all';

function saveTasks() {
    localStorage.setItem('tasks', JSON.stringify(tasks));
}

function renderTasks() {
    const taskList = document.getElementById('taskList');
    taskList.innerHTML = '';

    const filteredTasks = tasks.filter(task => {
        if (currentFilter === 'active') return !task.completed;
        if (currentFilter === 'completed') return task.completed;
        return true;
    });

    filteredTasks.forEach(task => {
        const li = document.createElement('li');
        li.className = 'task-item' + (task.completed ? ' completed' : '');
        li.innerHTML = `
            <input type="checkbox" ${task.completed ? 'checked' : ''}
                   onchange="toggleTask(${task.id})">
            <span class="task-text">${task.text}</span>
            <button class="delete-btn" onclick="deleteTask(${task.id})">Delete</button>
        `;
        taskList.appendChild(li);
    });

    updateStats();
}

function addTask() {
    const input = document.getElementById('taskInput');
    const text = input.value.trim();

    if (text === '') return;

    tasks.push({
        id: Date.now(),
        text: text,
        completed: false
    });

    input.value = '';
    saveTasks();
    renderTasks();
}

function toggleTask(id) {
    const task = tasks.find(t => t.id === id);
    if (task) {
        task.completed = !task.completed;
        saveTasks();
        renderTasks();
    }
}

function deleteTask(id) {
    tasks = tasks.filter(t => t.id !== id);
    saveTasks();
    renderTasks();
}

function filterTasks(filter) {
    currentFilter = filter;

    document.querySelectorAll('.filter-section button').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    renderTasks();
}

function clearCompleted() {
    tasks = tasks.filter(t => !t.completed);
    saveTasks();
    renderTasks();
}

function updateStats() {
    const remaining = tasks.filter(t => !t.completed).length;
    document.getElementById('taskCount').textContent =
        `${remaining} task${remaining !== 1 ? 's' : ''} remaining`;
}

document.getElementById('taskInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') addTask();
});

renderTasks();""",
            },
        ],
        "expense_tracker": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expense Tracker</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h1>💰 Expense Tracker</h1>

        <div class="balance-card">
            <div class="balance-item">
                <p>Income</p>
                <h2 class="income" id="totalIncome">$0</h2>
            </div>
            <div class="balance-item">
                <p>Expenses</p>
                <h2 class="expense" id="totalExpense">$0</h2>
            </div>
            <div class="balance-item">
                <p>Balance</p>
                <h2 id="balance">$0</h2>
            </div>
        </div>

        <div class="form-section">
            <h3>Add Transaction</h3>
            <input type="text" id="description" placeholder="Description">
            <input type="number" id="amount" placeholder="Amount">
            <select id="category">
                <option value="food">Food</option>
                <option value="transport">Transport</option>
                <option value="shopping">Shopping</option>
                <option value="salary">Salary</option>
                <option value="other">Other</option>
            </select>
            <div class="type-buttons">
                <button onclick="setType('income')" id="incomeBtn" class="active">Income</button>
                <button onclick="setType('expense')" id="expenseBtn">Expense</button>
            </div>
            <button onclick="addTransaction()" class="add-btn">Add Transaction</button>
        </div>

        <div class="transactions-section">
            <h3>Transaction History</h3>
            <ul id="transactionList"></ul>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 800px;
    margin: 30px auto;
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

h1 {
    text-align: center;
    color: #2d3748;
    margin-bottom: 30px;
}

.balance-card {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 30px;
}

.balance-item {
    background: #f7fafc;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
}

.balance-item p {
    color: #718096;
    margin-bottom: 10px;
}

.balance-item h2 {
    font-size: 1.8rem;
    color: #2d3748;
}

.income {
    color: #48bb78 !important;
}

.expense {
    color: #f56565 !important;
}

.form-section {
    background: #f7fafc;
    padding: 25px;
    border-radius: 10px;
    margin-bottom: 30px;
}

.form-section h3 {
    margin-bottom: 15px;
    color: #2d3748;
}

input, select {
    width: 100%;
    padding: 12px;
    margin-bottom: 15px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 16px;
}

.type-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 15px;
}

.type-buttons button {
    padding: 12px;
    background: #e2e8f0;
    color: #2d3748;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s;
}

.type-buttons button.active {
    background: #667eea;
    color: white;
}

.add-btn {
    width: 100%;
    padding: 15px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    cursor: pointer;
    transition: background 0.3s;
}

.add-btn:hover {
    background: #5a67d8;
}

.transactions-section h3 {
    margin-bottom: 15px;
    color: #2d3748;
}

#transactionList {
    list-style: none;
}

.transaction-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px;
    background: #f7fafc;
    margin-bottom: 10px;
    border-radius: 8px;
    border-left: 4px solid #667eea;
}

.transaction-item.income {
    border-left-color: #48bb78;
}

.transaction-item.expense {
    border-left-color: #f56565;
}

.transaction-info {
    flex: 1;
}

.transaction-amount {
    font-size: 1.2rem;
    font-weight: bold;
}

.transaction-amount.income {
    color: #48bb78;
}

.transaction-amount.expense {
    color: #f56565;
}

.delete-btn {
    padding: 8px 15px;
    background: #fed7d7;
    color: #c53030;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    margin-left: 10px;
}

.delete-btn:hover {
    background: #fc8181;
    color: white;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """let transactions = JSON.parse(localStorage.getItem('transactions')) || [];
let currentType = 'income';

function saveTransactions() {
    localStorage.setItem('transactions', JSON.stringify(transactions));
}

function setType(type) {
    currentType = type;
    document.getElementById('incomeBtn').classList.toggle('active', type === 'income');
    document.getElementById('expenseBtn').classList.toggle('active', type === 'expense');
}

function addTransaction() {
    const description = document.getElementById('description').value.trim();
    const amount = parseFloat(document.getElementById('amount').value);
    const category = document.getElementById('category').value;

    if (!description || !amount || amount <= 0) {
        alert('Please fill in all fields with valid values');
        return;
    }

    transactions.push({
        id: Date.now(),
        description,
        amount,
        category,
        type: currentType,
        date: new Date().toLocaleDateString()
    });

    document.getElementById('description').value = '';
    document.getElementById('amount').value = '';

    saveTransactions();
    renderTransactions();
    updateSummary();
}

function deleteTransaction(id) {
    transactions = transactions.filter(t => t.id !== id);
    saveTransactions();
    renderTransactions();
    updateSummary();
}

function renderTransactions() {
    const list = document.getElementById('transactionList');
    list.innerHTML = '';

    transactions.slice().reverse().forEach(t => {
        const li = document.createElement('li');
        li.className = `transaction-item ${t.type}`;
        li.innerHTML = `
            <div class="transaction-info">
                <strong>${t.description}</strong>
                <p>${t.category} • ${t.date}</p>
            </div>
            <span class="transaction-amount ${t.type}">
                ${t.type === 'income' ? '+' : '-'}$${t.amount.toFixed(2)}
            </span>
            <button class="delete-btn" onclick="deleteTransaction(${t.id})">×</button>
        `;
        list.appendChild(li);
    });
}

function updateSummary() {
    const income = transactions
        .filter(t => t.type === 'income')
        .reduce((sum, t) => sum + t.amount, 0);

    const expense = transactions
        .filter(t => t.type === 'expense')
        .reduce((sum, t) => sum + t.amount, 0);

    const balance = income - expense;

    document.getElementById('totalIncome').textContent = `$${income.toFixed(2)}`;
    document.getElementById('totalExpense').textContent = `$${expense.toFixed(2)}`;
    document.getElementById('balance').textContent = `$${balance.toFixed(2)}`;
}

renderTransactions();
updateSummary();""",
            },
        ],
        "student_management": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Management System</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h1>🎓 Student Management System</h1>

        <div class="form-section">
            <h3>Add / Edit Student</h3>
            <input type="hidden" id="editId">
            <input type="text" id="studentName" placeholder="Student Name" required>
            <input type="text" id="studentId" placeholder="Student ID" required>
            <select id="grade">
                <option value="">Select Grade</option>
                <option value="10">Grade 10</option>
                <option value="11">Grade 11</option>
                <option value="12">Grade 12</option>
            </select>
            <input type="text" id="major" placeholder="Major">
            <input type="email" id="email" placeholder="Email">
            <input type="tel" id="phone" placeholder="Phone Number">
            <button onclick="saveStudent()" id="saveBtn">Add Student</button>
            <button onclick="cancelEdit()" id="cancelBtn" style="display:none">Cancel</button>
        </div>

        <div class="search-section">
            <input type="text" id="searchInput" placeholder="Search by name or ID..." onkeyup="searchStudents()">
            <select id="gradeFilter" onchange="filterByGrade()">
                <option value="">All Grades</option>
                <option value="10">Grade 10</option>
                <option value="11">Grade 11</option>
                <option value="12">Grade 12</option>
            </select>
        </div>

        <div class="table-section">
            <table id="studentTable">
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Grade</th>
                        <th>Major</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="studentList"></tbody>
            </table>
        </div>

        <div class="stats">
            <span id="studentCount">Total: 0 students</span>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 30px auto;
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

h1 {
    text-align: center;
    color: #2d3748;
    margin-bottom: 30px;
}

.form-section {
    background: #f7fafc;
    padding: 25px;
    border-radius: 10px;
    margin-bottom: 30px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
}

.form-section h3 {
    grid-column: 1 / -1;
    color: #2d3748;
    margin-bottom: 10px;
}

input, select {
    padding: 12px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 16px;
}

button {
    padding: 12px 25px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: background 0.3s;
}

button:hover {
    background: #5a67d8;
}

#saveBtn, #cancelBtn {
    grid-column: 1 / -1;
}

#cancelBtn {
    background: #718096;
}

.search-section {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 15px;
    margin-bottom: 20px;
}

.table-section {
    overflow-x: auto;
    margin-bottom: 20px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

thead {
    background: #667eea;
    color: white;
}

th, td {
    padding: 15px;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
}

tbody tr:hover {
    background: #f7fafc;
}

.action-btn {
    padding: 6px 12px;
    margin: 0 5px;
    font-size: 14px;
}

.edit-btn {
    background: #48bb78;
}

.delete-btn {
    background: #f56565;
}

.stats {
    text-align: center;
    color: #718096;
    font-size: 18px;
    padding-top: 20px;
    border-top: 2px solid #e2e8f0;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """let students = JSON.parse(localStorage.getItem('students')) || [];
let editingId = null;

function saveStudents() {
    localStorage.setItem('students', JSON.stringify(students));
}

function saveStudent() {
    const name = document.getElementById('studentName').value.trim();
    const studentId = document.getElementById('studentId').value.trim();
    const grade = document.getElementById('grade').value;
    const major = document.getElementById('major').value.trim();
    const email = document.getElementById('email').value.trim();
    const phone = document.getElementById('phone').value.trim();

    if (!name || !studentId || !grade) {
        alert('Please fill in required fields: Name, Student ID, and Grade');
        return;
    }

    if (editingId) {
        const student = students.find(s => s.id === editingId);
        student.name = name;
        student.studentId = studentId;
        student.grade = grade;
        student.major = major;
        student.email = email;
        student.phone = phone;
        editingId = null;
    } else {
        students.push({
            id: Date.now(),
            name,
            studentId,
            grade,
            major,
            email,
            phone
        });
    }

    clearForm();
    saveStudents();
    renderStudents();
}

function editStudent(id) {
    const student = students.find(s => s.id === id);
    if (!student) return;

    document.getElementById('studentName').value = student.name;
    document.getElementById('studentId').value = student.studentId;
    document.getElementById('grade').value = student.grade;
    document.getElementById('major').value = student.major;
    document.getElementById('email').value = student.email;
    document.getElementById('phone').value = student.phone;

    editingId = id;
    document.getElementById('saveBtn').textContent = 'Update Student';
    document.getElementById('cancelBtn').style.display = 'block';
}

function deleteStudent(id) {
    if (confirm('Are you sure you want to delete this student?')) {
        students = students.filter(s => s.id !== id);
        saveStudents();
        renderStudents();
    }
}

function cancelEdit() {
    clearForm();
}

function clearForm() {
    document.getElementById('studentName').value = '';
    document.getElementById('studentId').value = '';
    document.getElementById('grade').value = '';
    document.getElementById('major').value = '';
    document.getElementById('email').value = '';
    document.getElementById('phone').value = '';
    editingId = null;
    document.getElementById('saveBtn').textContent = 'Add Student';
    document.getElementById('cancelBtn').style.display = 'none';
}

function searchStudents() {
    renderStudents();
}

function filterByGrade() {
    renderStudents();
}

function renderStudents() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const gradeFilter = document.getElementById('gradeFilter').value;

    const filtered = students.filter(s => {
        const matchesSearch = s.name.toLowerCase().includes(searchTerm) ||
                            s.studentId.toLowerCase().includes(searchTerm);
        const matchesGrade = !gradeFilter || s.grade === gradeFilter;
        return matchesSearch && matchesGrade;
    });

    const tbody = document.getElementById('studentList');
    tbody.innerHTML = '';

    filtered.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${s.studentId}</td>
            <td>${s.name}</td>
            <td>Grade ${s.grade}</td>
            <td>${s.major}</td>
            <td>${s.email}</td>
            <td>${s.phone}</td>
            <td>
                <button class="action-btn edit-btn" onclick="editStudent(${s.id})">Edit</button>
                <button class="action-btn delete-btn" onclick="deleteStudent(${s.id})">Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('studentCount').textContent =
        `Total: ${filtered.length} student${filtered.length !== 1 ? 's' : ''}`;
}

renderStudents();""",
            },
        ],
        "landing_page": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Modern Landing Page</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <nav>
            <div class="logo">MyBrand</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <section id="home" class="hero">
        <div class="hero-content">
            <h1>Welcome to the Future</h1>
            <p>Build amazing things with our cutting-edge platform</p>
            <button class="cta-button">Get Started</button>
        </div>
    </section>

    <section id="features" class="features">
        <h2>Our Features</h2>
        <div class="feature-grid">
            <div class="feature-card">
                <div class="icon">🚀</div>
                <h3>Fast Performance</h3>
                <p>Lightning-fast loading speeds for optimal user experience</p>
            </div>
            <div class="feature-card">
                <div class="icon">🔒</div>
                <h3>Secure</h3>
                <p>Enterprise-grade security to protect your data</p>
            </div>
            <div class="feature-card">
                <div class="icon">📱</div>
                <h3>Responsive</h3>
                <p>Works perfectly on all devices and screen sizes</p>
            </div>
            <div class="feature-card">
                <div class="icon">⚡</div>
                <h3>Easy to Use</h3>
                <p>Intuitive interface that anyone can master</p>
            </div>
        </div>
    </section>

    <section id="about" class="about">
        <h2>About Us</h2>
        <p>We are passionate about creating innovative solutions that make a difference. Our team of experts is dedicated to delivering excellence in everything we do.</p>
    </section>

    <section id="contact" class="contact">
        <h2>Contact Us</h2>
        <form class="contact-form">
            <input type="text" placeholder="Your Name" required>
            <input type="email" placeholder="Your Email" required>
            <textarea placeholder="Your Message" rows="5" required></textarea>
            <button type="submit">Send Message</button>
        </form>
    </section>

    <footer>
        <p>&copy; 2026 MyBrand. All rights reserved.</p>
    </footer>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1rem 0;
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

.logo {
    font-size: 1.5rem;
    font-weight: bold;
}

.nav-links {
    display: flex;
    list-style: none;
    gap: 2rem;
}

.nav-links a {
    color: white;
    text-decoration: none;
    transition: opacity 0.3s;
}

.nav-links a:hover {
    opacity: 0.8;
}

.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
}

.hero-content h1 {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.hero-content p {
    font-size: 1.5rem;
    margin-bottom: 2rem;
}

.cta-button {
    padding: 1rem 2rem;
    font-size: 1.2rem;
    background: white;
    color: #667eea;
    border: none;
    border-radius: 50px;
    cursor: pointer;
    transition: transform 0.3s;
}

.cta-button:hover {
    transform: scale(1.05);
}

section {
    padding: 5rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
}

h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
    color: #2d3748;
}

.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
}

.feature-card {
    background: #f7fafc;
    padding: 2rem;
    border-radius: 15px;
    text-align: center;
    transition: transform 0.3s, box-shadow 0.3s;
}

.feature-card:hover {
    transform: translateY(-10px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.feature-card h3 {
    margin-bottom: 1rem;
    color: #2d3748;
}

.about {
    background: #f7fafc;
}

.about p {
    text-align: center;
    font-size: 1.2rem;
    max-width: 800px;
    margin: 0 auto;
    color: #4a5568;
}

.contact-form {
    max-width: 600px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.contact-form input,
.contact-form textarea {
    padding: 1rem;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
}

.contact-form button {
    padding: 1rem 2rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1.1rem;
    cursor: pointer;
    transition: background 0.3s;
}

.contact-form button:hover {
    background: #5a67d8;
}

footer {
    background: #2d3748;
    color: white;
    text-align: center;
    padding: 2rem;
}

@media (max-width: 768px) {
    .nav-links {
        gap: 1rem;
    }

    .hero-content h1 {
        font-size: 2rem;
    }

    .hero-content p {
        font-size: 1.2rem;
    }
}""",
            },
        ],
        "personal_blog": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Personal Blog</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <h1>✍️ My Personal Blog</h1>
        <nav>
            <button onclick="showSection('home')">Home</button>
            <button onclick="showSection('create')">New Post</button>
        </nav>
    </header>

    <main id="home" class="section">
        <div class="filter-bar">
            <select id="categoryFilter" onchange="filterPosts()">
                <option value="">All Categories</option>
                <option value="technology">Technology</option>
                <option value="lifestyle">Lifestyle</option>
                <option value="travel">Travel</option>
                <option value="food">Food</option>
            </select>
        </div>

        <div id="postList" class="post-grid"></div>
    </main>

    <section id="create" class="section" style="display:none;">
        <div class="create-post-form">
            <h2>Create New Post</h2>
            <input type="text" id="postTitle" placeholder="Post Title">
            <select id="postCategory">
                <option value="technology">Technology</option>
                <option value="lifestyle">Lifestyle</option>
                <option value="travel">Travel</option>
                <option value="food">Food</option>
            </select>
            <textarea id="postContent" placeholder="Write your post content..." rows="10"></textarea>
            <button onclick="createPost()">Publish Post</button>
        </div>
    </section>

    <div id="postModal" class="modal" style="display:none;">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="postDetail"></div>
            <div class="comments-section">
                <h3>Comments</h3>
                <div id="commentList"></div>
                <div class="add-comment">
                    <input type="text" id="commentAuthor" placeholder="Your name">
                    <textarea id="commentText" placeholder="Your comment..." rows="3"></textarea>
                    <button onclick="addComment()">Add Comment</button>
                </div>
            </div>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #f7fafc;
    color: #2d3748;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

header h1 {
    margin-bottom: 1rem;
}

nav button {
    padding: 0.8rem 1.5rem;
    margin: 0 0.5rem;
    background: white;
    color: #667eea;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    font-size: 1rem;
    transition: transform 0.2s;
}

nav button:hover {
    transform: scale(1.05);
}

main {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 2rem;
}

.filter-bar {
    margin-bottom: 2rem;
}

select {
    padding: 0.8rem;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
    min-width: 200px;
}

.post-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 2rem;
}

.post-card {
    background: white;
    padding: 1.5rem;
    border-radius: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
}

.post-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 20px rgba(0,0,0,0.15);
}

.post-card h3 {
    color: #2d3748;
    margin-bottom: 0.5rem;
}

.post-meta {
    color: #718096;
    font-size: 0.9rem;
    margin-bottom: 1rem;
}

.category-badge {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    background: #667eea;
    color: white;
    border-radius: 15px;
    font-size: 0.8rem;
    margin-right: 0.5rem;
}

.post-excerpt {
    color: #4a5568;
    line-height: 1.6;
}

.create-post-form {
    max-width: 800px;
    margin: 0 auto;
    background: white;
    padding: 2rem;
    border-radius: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.create-post-form h2 {
    margin-bottom: 1.5rem;
    color: #2d3748;
}

.create-post-form input,
.create-post-form select,
.create-post-form textarea {
    width: 100%;
    padding: 1rem;
    margin-bottom: 1rem;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
}

.create-post-form button {
    width: 100%;
    padding: 1rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1.1rem;
    cursor: pointer;
    transition: background 0.3s;
}

.create-post-form button:hover {
    background: #5a67d8;
}

.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: white;
    padding: 2rem;
    border-radius: 15px;
    max-width: 800px;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
}

.close {
    position: absolute;
    right: 1rem;
    top: 1rem;
    font-size: 2rem;
    cursor: pointer;
    color: #718096;
}

.close:hover {
    color: #2d3748;
}

.comments-section {
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 2px solid #e2e8f0;
}

.comment {
    background: #f7fafc;
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 8px;
}

.comment-author {
    font-weight: bold;
    color: #2d3748;
    margin-bottom: 0.5rem;
}

.add-comment input,
.add-comment textarea {
    width: 100%;
    padding: 0.8rem;
    margin-bottom: 0.5rem;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
}

.add-comment button {
    padding: 0.8rem 1.5rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
}

.add-comment button:hover {
    background: #5a67d8;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """let posts = JSON.parse(localStorage.getItem('blogPosts')) || [];
let currentPostId = null;

function savePosts() {
    localStorage.setItem('blogPosts', JSON.stringify(posts));
}

function showSection(section) {
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    document.getElementById(section).style.display = 'block';
}

function createPost() {
    const title = document.getElementById('postTitle').value.trim();
    const category = document.getElementById('postCategory').value;
    const content = document.getElementById('postContent').value.trim();

    if (!title || !content) {
        alert('Please fill in title and content');
        return;
    }

    posts.push({
        id: Date.now(),
        title,
        category,
        content,
        author: 'Admin',
        date: new Date().toLocaleDateString(),
        comments: []
    });

    document.getElementById('postTitle').value = '';
    document.getElementById('postContent').value = '';

    savePosts();
    showSection('home');
    filterPosts();
}

function filterPosts() {
    const category = document.getElementById('categoryFilter').value;
    const filtered = category ? posts.filter(p => p.category === category) : posts;
    renderPosts(filtered);
}

function renderPosts(postsToRender) {
    const container = document.getElementById('postList');
    container.innerHTML = '';

    postsToRender.slice().reverse().forEach(post => {
        const card = document.createElement('div');
        card.className = 'post-card';
        card.onclick = () => showPost(post.id);

        const excerpt = post.content.substring(0, 150) + '...';

        card.innerHTML = `
            <span class="category-badge">${post.category}</span>
            <h3>${post.title}</h3>
            <div class="post-meta">${post.author} • ${post.date}</div>
            <p class="post-excerpt">${excerpt}</p>
        `;

        container.appendChild(card);
    });
}

function showPost(id) {
    const post = posts.find(p => p.id === id);
    if (!post) return;

    currentPostId = id;

    document.getElementById('postDetail').innerHTML = `
        <span class="category-badge">${post.category}</span>
        <h2>${post.title}</h2>
        <div class="post-meta">${post.author} • ${post.date}</div>
        <div style="margin-top: 1.5rem; line-height: 1.8;">${post.content}</div>
    `;

    renderComments(post.comments);
    document.getElementById('postModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('postModal').style.display = 'none';
    currentPostId = null;
}

function renderComments(comments) {
    const container = document.getElementById('commentList');
    container.innerHTML = '';

    comments.forEach(comment => {
        const div = document.createElement('div');
        div.className = 'comment';
        div.innerHTML = `
            <div class="comment-author">${comment.author}</div>
            <p>${comment.text}</p>
        `;
        container.appendChild(div);
    });
}

function addComment() {
    const author = document.getElementById('commentAuthor').value.trim();
    const text = document.getElementById('commentText').value.trim();

    if (!author || !text) {
        alert('Please fill in your name and comment');
        return;
    }

    const post = posts.find(p => p.id === currentPostId);
    if (!post) return;

    post.comments.push({ author, text });

    document.getElementById('commentAuthor').value = '';
    document.getElementById('commentText').value = '';

    savePosts();
    renderComments(post.comments);
}

filterPosts();""",
            },
        ],
        "snake_game": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Snake Game</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="game-container">
        <h1>🐍 Snake Game</h1>

        <div class="score-board">
            <div class="score">Score: <span id="score">0</span></div>
            <div class="high-score">High Score: <span id="highScore">0</span></div>
        </div>

        <canvas id="gameCanvas" width="400" height="400"></canvas>

        <div class="game-controls">
            <div id="gameStatus">Press SPACE to start</div>
            <button onclick="startGame()">Start Game</button>
            <button onclick="pauseGame()">Pause</button>
            <button onclick="resetGame()">Reset</button>
        </div>

        <div class="instructions">
            <h3>How to Play:</h3>
            <p>• Use Arrow Keys to move the snake</p>
            <p>• Eat the red food to grow</p>
            <p>• Don't hit the walls or yourself!</p>
            <p>• Press SPACE to start/pause</p>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.game-container {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    text-align: center;
}

h1 {
    color: #2d3748;
    margin-bottom: 20px;
}

.score-board {
    display: flex;
    justify-content: space-around;
    margin-bottom: 20px;
    font-size: 1.2rem;
}

.score, .high-score {
    padding: 10px 20px;
    background: #f7fafc;
    border-radius: 10px;
    color: #2d3748;
}

#score {
    color: #48bb78;
    font-weight: bold;
}

#highScore {
    color: #f56565;
    font-weight: bold;
}

#gameCanvas {
    border: 3px solid #2d3748;
    border-radius: 10px;
    background: #1a202c;
    display: block;
    margin: 0 auto 20px;
}

.game-controls {
    margin-bottom: 20px;
}

#gameStatus {
    font-size: 1.1rem;
    color: #2d3748;
    margin-bottom: 15px;
    font-weight: bold;
}

button {
    padding: 12px 25px;
    margin: 0 5px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
    transition: background 0.3s;
}

button:hover {
    background: #5a67d8;
}

.instructions {
    background: #f7fafc;
    padding: 20px;
    border-radius: 10px;
    text-align: left;
    max-width: 400px;
    margin: 0 auto;
}

.instructions h3 {
    color: #2d3748;
    margin-bottom: 10px;
}

.instructions p {
    color: #4a5568;
    margin: 5px 0;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const gridSize = 20;
const tileCount = canvas.width / gridSize;

let snake = [{x: 10, y: 10}];
let food = {x: 15, y: 15};
let dx = 0;
let dy = 0;
let score = 0;
let highScore = localStorage.getItem('snakeHighScore') || 0;
let gameRunning = false;
let gameLoop;

document.getElementById('highScore').textContent = highScore;

document.addEventListener('keydown', changeDirection);

function changeDirection(event) {
    const key = event.key;

    if (key === ' ') {
        event.preventDefault();
        gameRunning ? pauseGame() : startGame();
        return;
    }

    if (!gameRunning) return;

    if (key === 'ArrowUp' && dy === 0) {
        dx = 0; dy = -1;
    } else if (key === 'ArrowDown' && dy === 0) {
        dx = 0; dy = 1;
    } else if (key === 'ArrowLeft' && dx === 0) {
        dx = -1; dy = 0;
    } else if (key === 'ArrowRight' && dx === 0) {
        dx = 1; dy = 0;
    }
}

function startGame() {
    if (gameRunning) return;

    gameRunning = true;
    document.getElementById('gameStatus').textContent = 'Playing...';

    if (dx === 0 && dy === 0) {
        dx = 1;
        dy = 0;
    }

    gameLoop = setInterval(updateGame, 100);
}

function pauseGame() {
    gameRunning = false;
    clearInterval(gameLoop);
    document.getElementById('gameStatus').textContent = 'Paused - Press SPACE to continue';
}

function resetGame() {
    pauseGame();
    snake = [{x: 10, y: 10}];
    food = {x: 15, y: 15};
    dx = 0;
    dy = 0;
    score = 0;
    document.getElementById('score').textContent = score;
    document.getElementById('gameStatus').textContent = 'Press SPACE to start';
    drawGame();
}

function updateGame() {
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};

    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        gameOver();
        return;
    }

    for (let segment of snake) {
        if (head.x === segment.x && head.y === segment.y) {
            gameOver();
            return;
        }
    }

    snake.unshift(head);

    if (head.x === food.x && head.y === food.y) {
        score++;
        document.getElementById('score').textContent = score;

        if (score > highScore) {
            highScore = score;
            localStorage.setItem('snakeHighScore', highScore);
            document.getElementById('highScore').textContent = highScore;
        }

        spawnFood();
    } else {
        snake.pop();
    }

    drawGame();
}

function spawnFood() {
    food = {
        x: Math.floor(Math.random() * tileCount),
        y: Math.floor(Math.random() * tileCount)
    };

    for (let segment of snake) {
        if (food.x === segment.x && food.y === segment.y) {
            spawnFood();
            return;
        }
    }
}

function drawGame() {
    ctx.fillStyle = '#1a202c';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#48bb78';
    snake.forEach((segment, index) => {
        ctx.fillRect(
            segment.x * gridSize,
            segment.y * gridSize,
            gridSize - 2,
            gridSize - 2
        );

        if (index === 0) {
            ctx.fillStyle = '#38a169';
            ctx.fillRect(
                segment.x * gridSize + 4,
                segment.y * gridSize + 4,
                gridSize - 10,
                gridSize - 10
            );
            ctx.fillStyle = '#48bb78';
        }
    });

    ctx.fillStyle = '#f56565';
    ctx.fillRect(
        food.x * gridSize,
        food.y * gridSize,
        gridSize - 2,
        gridSize - 2
    );
}

function gameOver() {
    pauseGame();
    document.getElementById('gameStatus').textContent = `Game Over! Score: ${score}`;
}

drawGame();""",
            },
        ],
        "flappy_bird": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flappy Bird Clone</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="game-container">
        <h1>🐦 Flappy Bird</h1>

        <div class="score-display">
            <div class="current-score">Score: <span id="score">0</span></div>
            <div class="best-score">Best: <span id="bestScore">0</span></div>
        </div>

        <canvas id="gameCanvas" width="400" height="600"></canvas>

        <div class="controls">
            <div id="status">Click or Press SPACE to start</div>
            <button onclick="restartGame()">Restart</button>
        </div>

        <div class="instructions">
            <h3>How to Play:</h3>
            <p>• Click or Press SPACE to flap</p>
            <p>• Avoid the pipes</p>
            <p>• Get the highest score!</p>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.game-container {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    text-align: center;
}

h1 {
    color: #2d3748;
    margin-bottom: 20px;
}

.score-display {
    display: flex;
    justify-content: space-around;
    margin-bottom: 20px;
    font-size: 1.3rem;
}

.current-score, .best-score {
    padding: 12px 25px;
    background: #f7fafc;
    border-radius: 10px;
    color: #2d3748;
}

#score {
    color: #667eea;
    font-weight: bold;
}

#bestScore {
    color: #f6ad55;
    font-weight: bold;
}

#gameCanvas {
    border: 3px solid #2d3748;
    border-radius: 10px;
    background: linear-gradient(to bottom, #87ceeb 0%, #e0f6ff 100%);
    cursor: pointer;
    display: block;
    margin: 0 auto 20px;
}

.controls {
    margin-bottom: 20px;
}

#status {
    font-size: 1.1rem;
    color: #2d3748;
    margin-bottom: 15px;
    font-weight: bold;
}

button {
    padding: 12px 30px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
    transition: background 0.3s;
}

button:hover {
    background: #5a67d8;
}

.instructions {
    background: #f7fafc;
    padding: 20px;
    border-radius: 10px;
    text-align: left;
    max-width: 400px;
    margin: 0 auto;
}

.instructions h3 {
    color: #2d3748;
    margin-bottom: 10px;
}

.instructions p {
    color: #4a5568;
    margin: 5px 0;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const bird = {
    x: 50,
    y: canvas.height / 2,
    width: 30,
    height: 30,
    velocity: 0,
    gravity: 0.5,
    jump: -8
};

let pipes = [];
let score = 0;
let bestScore = localStorage.getItem('flappyBestScore') || 0;
let gameState = 'ready'; // ready, playing, gameOver
let frameCount = 0;

document.getElementById('bestScore').textContent = bestScore;

canvas.addEventListener('click', handleInput);
document.addEventListener('keydown', (e) => {
    if (e.code === 'Space') {
        e.preventDefault();
        handleInput();
    }
});

function handleInput() {
    if (gameState === 'ready') {
        startGame();
    } else if (gameState === 'playing') {
        bird.velocity = bird.jump;
    } else if (gameState === 'gameOver') {
        restartGame();
    }
}

function startGame() {
    gameState = 'playing';
    document.getElementById('status').textContent = 'Flying...';
    requestAnimationFrame(gameLoop);
}

function restartGame() {
    bird.y = canvas.height / 2;
    bird.velocity = 0;
    pipes = [];
    score = 0;
    frameCount = 0;
    document.getElementById('score').textContent = score;
    gameState = 'ready';
    document.getElementById('status').textContent = 'Click or Press SPACE to start';
    draw();
}

function gameLoop() {
    if (gameState !== 'playing') return;

    update();
    draw();
    frameCount++;

    requestAnimationFrame(gameLoop);
}

function update() {
    bird.velocity += bird.gravity;
    bird.y += bird.velocity;

    if (bird.y + bird.height > canvas.height || bird.y < 0) {
        endGame();
        return;
    }

    if (frameCount % 90 === 0) {
        const gap = 150;
        const minHeight = 50;
        const maxHeight = canvas.height - gap - minHeight;
        const pipeHeight = Math.random() * (maxHeight - minHeight) + minHeight;

        pipes.push({
            x: canvas.width,
            top: pipeHeight,
            bottom: pipeHeight + gap,
            width: 50,
            scored: false
        });
    }

    pipes.forEach((pipe, index) => {
        pipe.x -= 2;

        if (pipe.x + pipe.width < 0) {
            pipes.splice(index, 1);
        }

        if (!pipe.scored && pipe.x + pipe.width < bird.x) {
            score++;
            pipe.scored = true;
            document.getElementById('score').textContent = score;

            if (score > bestScore) {
                bestScore = score;
                localStorage.setItem('flappyBestScore', bestScore);
                document.getElementById('bestScore').textContent = bestScore;
            }
        }

        if (bird.x < pipe.x + pipe.width &&
            bird.x + bird.width > pipe.x &&
            (bird.y < pipe.top || bird.y + bird.height > pipe.bottom)) {
            endGame();
        }
    });
}

function draw() {
    ctx.fillStyle = '#87ceeb';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#f6ad55';
    ctx.fillRect(bird.x, bird.y, bird.width, bird.height);

    ctx.fillStyle = '#2d3748';
    ctx.fillRect(bird.x + 5, bird.y + 5, 8, 8);

    ctx.fillStyle = '#48bb78';
    pipes.forEach(pipe => {
        ctx.fillRect(pipe.x, 0, pipe.width, pipe.top);
        ctx.fillRect(pipe.x, pipe.bottom, pipe.width, canvas.height - pipe.bottom);

        ctx.fillStyle = '#38a169';
        ctx.fillRect(pipe.x, pipe.top - 20, pipe.width, 20);
        ctx.fillRect(pipe.x, pipe.bottom, pipe.width, 20);
        ctx.fillStyle = '#48bb78';
    });
}

function endGame() {
    gameState = 'gameOver';
    document.getElementById('status').textContent = `Game Over! Final Score: ${score}`;
}

draw();""",
            },
        ],
        "memory_card": [
            {
                "path": "index.html",
                "name": "index.html",
                "type": "file",
                "language": "html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memory Card Game</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="game-container">
        <h1>🎮 Memory Card Game</h1>

        <div class="game-stats">
            <div class="stat">
                <span>Moves:</span>
                <span id="moves">0</span>
            </div>
            <div class="stat">
                <span>Matches:</span>
                <span id="matches">0/8</span>
            </div>
            <div class="stat">
                <span>Time:</span>
                <span id="time">0:00</span>
            </div>
        </div>

        <div id="gameBoard" class="game-board"></div>

        <div class="controls">
            <button onclick="startNewGame()">New Game</button>
            <button onclick="resetGame()">Reset</button>
        </div>

        <div id="winMessage" class="win-message" style="display:none;">
            <h2>🎉 You Won!</h2>
            <p>Moves: <span id="finalMoves"></span></p>
            <p>Time: <span id="finalTime"></span></p>
            <button onclick="startNewGame()">Play Again</button>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>""",
            },
            {
                "path": "styles.css",
                "name": "styles.css",
                "type": "file",
                "language": "css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.game-container {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    text-align: center;
    max-width: 600px;
}

h1 {
    color: #2d3748;
    margin-bottom: 20px;
}

.game-stats {
    display: flex;
    justify-content: space-around;
    margin-bottom: 30px;
    background: #f7fafc;
    padding: 15px;
    border-radius: 10px;
}

.stat {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.stat span:first-child {
    color: #718096;
    font-size: 0.9rem;
}

.stat span:last-child {
    color: #2d3748;
    font-size: 1.5rem;
    font-weight: bold;
}

.game-board {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 30px;
}

.card {
    aspect-ratio: 1;
    background: #667eea;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    transition: transform 0.3s, background 0.3s;
    position: relative;
}

.card:hover:not(.flipped):not(.matched) {
    transform: scale(1.05);
    background: #5a67d8;
}

.card.flipped,
.card.matched {
    background: white;
    border: 3px solid #667eea;
}

.card.matched {
    background: #c3dafe;
    border-color: #48bb78;
    cursor: default;
}

.card-back {
    display: block;
}

.card.flipped .card-back,
.card.matched .card-back {
    display: none;
}

.card-front {
    display: none;
}

.card.flipped .card-front,
.card.matched .card-front {
    display: block;
}

.controls {
    display: flex;
    gap: 10px;
    justify-content: center;
}

button {
    padding: 12px 30px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
    transition: background 0.3s;
}

button:hover {
    background: #5a67d8;
}

.win-message {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: white;
    padding: 40px;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    z-index: 1000;
    text-align: center;
}

.win-message h2 {
    color: #48bb78;
    margin-bottom: 20px;
}

.win-message p {
    font-size: 1.2rem;
    margin: 10px 0;
    color: #2d3748;
}

.win-message button {
    margin-top: 20px;
}""",
            },
            {
                "path": "app.js",
                "name": "app.js",
                "type": "file",
                "language": "javascript",
                "content": """const symbols = ['🎮', '🎯', '🎲', '🎪', '🎨', '🎭', '🎬', '🎸'];
let cards = [];
let flippedCards = [];
let matchedPairs = 0;
let moves = 0;
let startTime;
let timerInterval;

function shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

function createBoard() {
    const gameBoard = document.getElementById('gameBoard');
    gameBoard.innerHTML = '';

    const cardPairs = [...symbols, ...symbols];
    cards = shuffleArray(cardPairs);

    cards.forEach((symbol, index) => {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.index = index;
        card.innerHTML = `
            <span class="card-back">?</span>
            <span class="card-front">${symbol}</span>
        `;
        card.addEventListener('click', () => flipCard(card, index));
        gameBoard.appendChild(card);
    });
}

function flipCard(cardElement, index) {
    if (flippedCards.length === 2) return;
    if (cardElement.classList.contains('flipped')) return;
    if (cardElement.classList.contains('matched')) return;

    if (flippedCards.length === 0) {
        startTimer();
    }

    cardElement.classList.add('flipped');
    flippedCards.push({ element: cardElement, index, symbol: cards[index] });

    if (flippedCards.length === 2) {
        moves++;
        document.getElementById('moves').textContent = moves;
        checkMatch();
    }
}

function checkMatch() {
    const [card1, card2] = flippedCards;

    if (card1.symbol === card2.symbol) {
        card1.element.classList.add('matched');
        card2.element.classList.add('matched');
        card1.element.classList.remove('flipped');
        card2.element.classList.remove('flipped');

        matchedPairs++;
        document.getElementById('matches').textContent = `${matchedPairs}/8`;

        flippedCards = [];

        if (matchedPairs === 8) {
            setTimeout(showWinMessage, 500);
        }
    } else {
        setTimeout(() => {
            card1.element.classList.remove('flipped');
            card2.element.classList.remove('flipped');
            flippedCards = [];
        }, 1000);
    }
}

function startTimer() {
    if (startTime) return;

    startTime = Date.now();
    timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        document.getElementById('time').textContent =
            `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
}

function showWinMessage() {
    stopTimer();
    const timeText = document.getElementById('time').textContent;
    document.getElementById('finalMoves').textContent = moves;
    document.getElementById('finalTime').textContent = timeText;
    document.getElementById('winMessage').style.display = 'block';
}

function startNewGame() {
    resetGame();
    document.getElementById('winMessage').style.display = 'none';
}

function resetGame() {
    flippedCards = [];
    matchedPairs = 0;
    moves = 0;
    startTime = null;
    stopTimer();

    document.getElementById('moves').textContent = '0';
    document.getElementById('matches').textContent = '0/8';
    document.getElementById('time').textContent = '0:00';

    createBoard();
}

createBoard();""",
            },
        ],
    }

    # Insert templates
    print("Seeding templates...")
    for template in templates:
        existing = db.software_lab_templates.find_one({"id": template["id"]})
        if existing:
            print(f"  ⚠️  Template '{template['name']}' already exists, skipping...")
        else:
            db.software_lab_templates.insert_one(template)
            print(f"  ✅ Seeded template: {template['name']}")

    # Insert template files
    print("\nSeeding template files...")
    for template_id, files in template_files.items():
        for file_data in files:
            file_doc = {
                "id": f"tf_{secrets.token_hex(8)}",  # Generate unique ID
                "template_id": template_id,
                **file_data,
                "created_at": datetime.utcnow(),
            }

            existing = db.software_lab_template_files.find_one(
                {"template_id": template_id, "path": file_data["path"]}
            )

            if existing:
                print(
                    f"  ⚠️  File '{file_data['path']}' for '{template_id}' exists, skipping..."
                )
            else:
                db.software_lab_template_files.insert_one(file_doc)
                print(f"  ✅ Seeded file: {template_id}/{file_data['path']}")

    print("\n✅ All 9 templates seeded successfully!")
    print("\nTemplate Summary:")
    print("  Mobile Apps: Calculator, Todo List, Expense Tracker")
    print("  Websites: Student Management, Landing Page, Personal Blog")
    print("  Games: Snake, Flappy Bird, Memory Card")


if __name__ == "__main__":
    seed_all_templates()
