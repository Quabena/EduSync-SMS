# 🎓 EduSync-SMS

**ALX Final Portfolio Project**

EduSync-SMS is a modern School Management System (SMS) designed to streamline and digitize school operations such as attendance, class management, grading, and user authentication. Built with Flask and tailored for educational institutions, EduSync offers modularity, usability, and scalability.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Roles & Permissions](#roles--permissions)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

EduSync-SMS is a capstone portfolio project for the ALX Software Engineering Program. It demonstrates full-stack development skills by providing a robust web-based school management platform with real-world utility.

---

## Features

- 🔐 User authentication and role-based access (`admin`, `headteacher`, `teacher`)
- Class and student information management
- Class scheduling (basic structure)
- QR-based and manual attendance tracking
- Grade and performance tracking (planned module)
- Admin dashboard for managing staff and operations

---

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy
- **Frontend**: Jinja2, Tailwind CSS, JavaScript
- **Database**: SQLite (dev) / PostgreSQL / MySQL (optional)
- **Auth**: Flask-Login, Flask-WTF

---

## Installation

### Prerequisites

- Python 3.12+
- Virtualenv (recommended)

### Steps

```bash
# Clone the repository
git clone https://github.com/Quabena/EduSync-SMS.git
cd EduSync-SMS

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize the database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Start the server
flask run
```

---

## Usage

Access the application at: [http://localhost:5000](http://localhost:5000)

You may register as an admin or create users from the database or admin interface. The system supports:

- Taking attendance by QR code or manual interface
- Assigning class teachers
- Viewing student lists per class

---

## Roles & Permissions

| Role        | Capabilities                                     |
| ----------- | ------------------------------------------------ |
| Admin       | Full access: user/class/attendance management    |
| Headteacher | Manage classes, assign teachers, take attendance |
| Teacher     | Take/view attendance for assigned classes        |

---

## Contributing

Contributions are welcome!

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m "Add AmazingFeature"`
4. Push to GitHub: `git push origin feature/AmazingFeature`
5. Open a pull request

---

## License

This project is currently **unlicensed**. Please contact the owner for usage or contribution permissions.

---

## Contact

- **GitHub Repository**: [EduSync-SMS](https://github.com/Quabena/EduSync-SMS)
- **Maintainer**: [Quabena](https://github.com/Quabena)
