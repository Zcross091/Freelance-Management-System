# 🚀 Freelance Management System (Hostel Edition)

A robust, automated Discord-based ecosystem designed to manage "labor-based" businesses in a hostel environment. This system replaces manual tracking (WhatsApp/Excel) with a structured SQLite database and a multi-bot architecture.

## ## 📑 Overview
This system is divided into three functional "Bots" running under a single Python process to ensure seamless communication and data integrity:

*   **Bot A (The Intake):** Handles professional order collection via Discord Modals.
*   **Bot B (The Dispatcher):** Manages task assignment using a reaction-based claim system with race-condition protection.
*   **Bot C (The CFO/Tracker):** Automates commission calculations, manages payout ledgers, and handles financial "settlements."

## ## 🛠 Tech Stack
*   **Language:** Python 3.x
*   **Library:** `discord.py` (API wrapper)
*   **Database:** SQLite3 (Persistent relational storage)
*   **Environment:** Linux (Optimized for Oracle Cloud VPS)
*   **Process Management:** PM2 (For 24/7 uptime)

---

## ## ✨ Key Features

### ### 1. Professional Order Intake
Instead of messy chat threads, "The Guy" uses the `/new_order` command to trigger a pop-up modal. This ensures every job has a:
*   Unique **Ticket ID**
*   Specified **Budget**
*   Clear **Deadline**
*   Stored **Description**

### ### 2. Claim System (Anti-Race Condition)
Workers claim jobs by reacting with 👍. 
*   **Logic:** The system performs a database check at the millisecond of the reaction.
*   **Security:** If two workers react simultaneously, the database only authorizes the first one, preventing double-assignments.

### ### 3. The "CFO" Ledger (Admin's Commission)
The system uses a unique **Page-Based Commission Model**:
*   **Tracker:** Automatically calculates management fees based on a ₹1/page rate.
*   **Live Balance:** `/payouts` shows exactly what is currently owed to the administrator.
*   **The Settle Command:** A professional `/settle` feature that clears the unpaid balance once the cash is received, moving records to a "SETTLED" state for permanent archiving.

### ### 4. Auto-Cleanup
To maintain a high-performance environment, the bot automatically deletes job advertisements from the worker channel once they are marked as `/complete`, ensuring the team only sees active opportunities.

---

## ## 📂 Database Schema
The system operates on a relational `assignments` table:
*   `ticket_id`: Primary Key (Auto-increment)
*   `status`: (OPEN, CLAIMED, PAID, SETTLED)
*   `page_count`: Integer (Used for commission math)
*   `message_id`: Reference for Discord UI updates

---

## ## 🛡 Security & Privacy
*   **Admin-Locked:** Financial reports and settlement commands are restricted to a specific `ADMIN_ID`.
*   **Environment Safety:** Sensitive tokens and local database files are excluded from version control via `.gitignore`.

---

## ## 🚀 Deployment
Currently hosted on an **Oracle Cloud VPS** using **PM2** for continuous operation and **GitHub** for version-controlled deployment.

---
*Created by Yahya - CSE Portfolio Project*
