# Database Management Guide
## Smart Attendance System - Complete Database Architecture

---

## 📋 Table of Contents
1. [Database Technology Overview](#database-technology-overview)
2. [Architecture & Design Principles](#architecture--design-principles)
3. [Schema Design & Table Structure](#schema-design--table-structure)
4. [DatabaseManager Class Explained](#databasemanager-class-explained)
5. [SQL Queries & Operations](#sql-queries--operations)
6. [Indexing Strategy](#indexing-strategy)
7. [Connection Management](#connection-management)
8. [Data Integrity & Constraints](#data-integrity--constraints)
9. [Common Database Operations](#common-database-operations)
10. [Performance Optimization](#performance-optimization)
11. [Troubleshooting & Best Practices](#troubleshooting--best-practices)
12. [FAQs for Database Developers](#faqs-for-database-developers)

---

## 🛠️ Database Technology Overview

### Core Technology: SQLite 3

**What is SQLite?**
- **Serverless**: No separate database process - embedded in application
- **File-based**: Single file stores entire database
- **ACID Compliant**: Atomicity, Consistency, Isolation, Durability
- **Zero Configuration**: No setup, no admin overhead
- **Cross-Platform**: Works on Windows, Linux, macOS
- **Public Domain**: Free to use, no licensing

**Why SQLite for This System?**

| Requirement | SQLite Solution |
|------------|-----------------|
| **Simplicity** | Single file deployment - no server setup |
| **Portability** | Copy database file = full backup |
| **Reliability** | ACID transactions prevent corruption |
| **Performance** | Faster than client-server for local access |
| **Concurrent Access** | WAL mode enables multiple readers + 1 writer |
| **Size** | Compact (our DB ~100KB with 100 students) |

**When SQLite Works Best:**
- ✅ Small to medium applications (< 100K records)
- ✅ Read-heavy workloads (perfect for attendance queries)
- ✅ Local/embedded deployments
- ✅ Single-user or low-concurrency scenarios

**When to Consider PostgreSQL/MySQL:**
- ❌ High concurrent writes (> 10 simultaneous write operations)
- ❌ Multi-server deployments (distributed systems)
- ❌ Very large datasets (> 1 million records frequently accessed)

**For our attendance system**: SQLite is perfect! We have:
- Moderate data size (hundreds to thousands of records)
- Read-heavy operations (viewing reports)
- Occasional writes (marking attendance)
- Simple deployment (no database server needed)

---

## 🏗️ Architecture & Design Principles

### 1. **Single Responsibility Pattern**

Each table has one clear purpose:
```
students       → Student registry (master data)
entry_log      → Entry timestamps (transaction log)
exit_log       → Exit timestamps (transaction log)
attendance     → Calculated sessions (reporting/analytics)
system_settings → Configuration persistence
```

### 2. **Connection Pooling via Context Manager**

**Principle**: Always close database connections to prevent file locks

```python
class _SQLiteConnectionContext:
    """Ensures connections are always closed, even on errors"""
    
    def __enter__(self):
        return self._connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._connection.commit()  # Success
            else:
                self._connection.rollback()  # Error occurred
        finally:
            self._connection.close()  # ALWAYS close
        return False
```

**Why This Matters:**
- Prevents "database is locked" errors
- Automatic rollback on exceptions
- No leaked connections
- Safe concurrent access

### 3. **Write-Ahead Logging (WAL) Mode**

**What is WAL?**
- Changes written to separate log file first
- Main database updated asynchronously
- Enables concurrent readers during writes
- Better crash recovery

```python
conn.execute("PRAGMA journal_mode = WAL")
```

**Benefits:**
- Multiple simultaneous reads
- One concurrent write
- Faster performance (30-50% improvement)
- No "database is locked" for readers

**Trade-off:**
- Requires 3 files instead of 1:
  - `attendance.db` (main database)
  - `attendance.db-wal` (write-ahead log)
  - `attendance.db-shm` (shared memory index)

### 4. **Foreign Key Constraints**

**Principle**: Data integrity through relationships

```sql
FOREIGN KEY (student_id) REFERENCES students(student_id)
```

**What This Does:**
- Can't mark attendance for non-existent student
- Prevents orphaned records (entry without student)
- Cascading options (delete student → delete attendance)

**Enabled By:**
```python
conn.execute("PRAGMA foreign_keys = ON")
```

⚠️ **Critical**: SQLite disables foreign keys by default! We enable them explicitly.

---

## 📊 Schema Design & Table Structure

### Table 1: `students` (Master Data)

**Purpose**: Registry of all registered students

```sql
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,          -- Format: "student_2301105225_John_Doe"
    name TEXT NOT NULL,                   -- Full name: "Asish Kumar Sahoo"
    roll_number TEXT UNIQUE NOT NULL,     -- University roll: "2301105225"
    registered_date TEXT NOT NULL         -- ISO format: "2026-03-03T10:30:00"
)
```

**Design Decisions:**

| Column | Type | Why? |
|--------|------|------|
| `student_id` | TEXT | Composite key with name for folder identification |
| `name` | TEXT | Human-readable identifier |
| `roll_number` | TEXT | Unique identifier (not INTEGER to preserve leading zeros) |
| `registered_date` | TEXT | SQLite date storage (ISO 8601 format) |

**Constraints:**
- `PRIMARY KEY` on `student_id` → Ensures uniqueness
- `UNIQUE` on `roll_number` → No duplicate enrollments
- `NOT NULL` on all fields → No incomplete registrations

**Sample Data:**
```sql
INSERT INTO students VALUES 
('student_2301105225_Asish_Kumar_Sahoo', 'Asish Kumar Sahoo', '2301105225', '2026-02-28T15:30:00'),
('student_2301105266_Roshan_Maharana', 'Roshan Maharana', '2301105266', '2026-03-01T09:15:00');
```

---

### Table 2: `entry_log` (Entry Transactions)

**Purpose**: Record every entry into the system

```sql
CREATE TABLE entry_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incrementing ID
    student_id TEXT NOT NULL,              -- Links to students table
    name TEXT NOT NULL,                    -- Denormalized for performance
    entry_time TEXT NOT NULL,              -- Timestamp: "2026-03-03T09:05:30"
    date TEXT NOT NULL,                    -- Date only: "2026-03-03"
    subject TEXT NOT NULL DEFAULT 'Operating System',  -- Class subject
    status TEXT NOT NULL DEFAULT 'INSIDE', -- INSIDE or EXITED
    FOREIGN KEY (student_id) REFERENCES students(student_id)
)
```

**Design Decisions:**

**Why denormalize `name`?**
- Avoids JOIN for every query
- Faster reports (trade space for speed)
- Name rarely changes

**Why separate `date` from `entry_time`?**
- Faster daily reports (indexed on date)
- Easy date-range queries
- Date is part of composite index

**Status Field:**
- `INSIDE`: Student entered, hasn't exited (active session)
- `EXITED`: Student has exited (session complete)

**Why This Matters:**
- Prevents duplicate entries (can't enter twice in one day for same subject)
- Tracks active sessions
- Links to exit_log via id

**Sample Data:**
```sql
INSERT INTO entry_log (student_id, name, entry_time, date, subject, status) VALUES
('student_2301105225_Asish_Kumar_Sahoo', 'Asish Kumar Sahoo', '2026-03-03T09:05:30', '2026-03-03', 'Data Science', 'EXITED'),
('student_2301105266_Roshan_Maharana', 'Roshan Maharana', '2026-03-03T09:06:15', '2026-03-03', 'Data Science', 'INSIDE');
```

**Unique Constraint:**
```sql
CREATE UNIQUE INDEX idx_entry_unique_inside_per_subject
ON entry_log (student_id, date, subject)
WHERE status = 'INSIDE'
```

This prevents:
- Same student entering twice for same subject on same day
- Duplicate active sessions

---

### Table 3: `exit_log` (Exit Transactions)

**Purpose**: Record every exit from the system

```sql
CREATE TABLE exit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entry_id INTEGER NOT NULL,            -- Links to entry_log(id)
    exit_time TEXT NOT NULL,
    date TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (entry_id) REFERENCES entry_log(id)
)
```

**Design Decisions:**

**Why `entry_id`?**
- Links exit to specific entry
- Calculates session duration
- Handles same-day multiple sessions

**Workflow:**
1. Student enters → Record in `entry_log` (status = 'INSIDE')
2. Student exits → Record in `exit_log` with entry_id
3. Update `entry_log` status to 'EXITED'
4. Calculate duration and insert into `attendance`

**Sample Data:**
```sql
INSERT INTO exit_log (student_id, name, entry_id, exit_time, date) VALUES
('student_2301105225_Asish_Kumar_Sahoo', 'Asish Kumar Sahoo', 1, '2026-03-03T11:05:30', '2026-03-03');
```

---

### Table 4: `attendance` (Calculated Sessions)

**Purpose**: Final attendance records with durations

```sql
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL,
    duration INTEGER NOT NULL CHECK(duration >= 0),  -- Seconds
    status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT')),
    date TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT 'Operating System',
    FOREIGN KEY (student_id) REFERENCES students(student_id)
)
```

**Design Decisions:**

**Why separate `attendance` table?**
- Reporting optimization (pre-calculated durations)
- Clean separation: logs vs. analytics
- Easy to query "who was present on X date?"

**Duration Calculation:**
```python
entry_time = datetime.fromisoformat("2026-03-03T09:05:30")
exit_time = datetime.fromisoformat("2026-03-03T11:05:30")
duration = int((exit_time - entry_time).total_seconds())  # 7200 seconds = 2 hours
```

**Status Logic:**
```python
if duration >= MINIMUM_DURATION:  # e.g., 30 minutes
    status = 'PRESENT'
else:
    status = 'ABSENT'  # Too short to count
```

**CHECK Constraints:**
- `duration >= 0`: No negative durations
- `status IN ('PRESENT', 'ABSENT')`: Only valid statuses

**Sample Data:**
```sql
INSERT INTO attendance (student_id, name, entry_time, exit_time, duration, status, date, subject) VALUES
('student_2301105225_Asish_Kumar_Sahoo', 'Asish Kumar Sahoo', 
 '2026-03-03T09:05:30', '2026-03-03T11:05:30', 7200, 'PRESENT', '2026-03-03', 'Data Science');
```

---

### Table 5: `system_settings` (Configuration)

**Purpose**: Persist system configuration

```sql
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

**Design Decisions:**

**Why TEXT for values?**
- Flexible storage (strings, numbers, booleans)
- No schema changes for new settings
- Parse on retrieval

**Default Settings:**
```python
{
    "camera_policy": "on-demand-scan",      # or "session-based"
    "camera_run_mode": "once",               # or "interval"
    "active_subject": "Operating System",
    "run_interval_seconds": "300",           # 5 minutes
    "session_duration_minutes": "50"         # Class duration
}
```

**Sample Data:**
```sql
INSERT INTO system_settings (key, value, updated_at) VALUES
('camera_policy', 'on-demand-scan', '2026-03-03T08:00:00'),
('active_subject', 'Data Science', '2026-03-03T09:00:00');
```

---

## 🔧 DatabaseManager Class Explained

### Class Structure

```python
class DatabaseManager:
    """Centralized database operations for the attendance system."""
    
    def __init__(self):
        self.db_path = config.DATABASE_FILE  # "data/database/attendance.db"
        self._ensure_database_directory()    # Create folder if needed
        self.create_tables()                 # Initialize schema
```

### Connection Configuration

```python
def get_connection(self):
    conn = sqlite3.connect(
        self.db_path, 
        timeout=30.0,              # Wait 30s for locks to clear
        check_same_thread=False    # Allow multi-threading
    )
    
    # Performance optimizations
    conn.execute("PRAGMA journal_mode = WAL")       # Enable WAL
    conn.execute("PRAGMA busy_timeout = 30000")     # 30s busy timeout
    conn.execute("PRAGMA synchronous = NORMAL")     # Balance safety/speed
    conn.execute("PRAGMA cache_size = -64000")      # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY")      # Temp in RAM
    conn.execute("PRAGMA foreign_keys = ON")        # Enable FK checks
    
    return _SQLiteConnectionContext(conn)
```

**PRAGMA Explanations:**

| PRAGMA | Value | Purpose | Impact |
|--------|-------|---------|--------|
| `journal_mode` | WAL | Write-ahead logging | Concurrent reads, faster writes |
| `busy_timeout` | 30000ms | Wait time for locks | Reduces "database locked" errors |
| `synchronous` | NORMAL | Sync after checkpoints | 2x faster than FULL, still safe |
| `cache_size` | -64000 | 64MB cache | Faster queries (more RAM usage) |
| `temp_store` | MEMORY | Temp tables in RAM | Faster sorting/joins |
| `foreign_keys` | ON | Enforce FK constraints | Data integrity |

---

## 📝 SQL Queries & Operations

### Common Query Patterns

**1. Register Student**

```python
def register_student(self, student_id: str, name: str, roll_number: str) -> bool:
    """Register a new student in the system."""
    try:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            
            cursor.execute(
                """
                INSERT INTO students (student_id, name, roll_number, registered_date)
                VALUES (?, ?, ?, ?)
                """,
                (student_id, name, roll_number, now)
            )
            return True
            
    except sqlite3.IntegrityError as e:
        # Duplicate roll_number
        logger.error(f"Student already registered: {e}")
        return False
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return False
```

**Key Points:**
- **Parameterized queries** (`?` placeholders) prevent SQL injection
- **Context manager** auto-commits on success, rolls back on error
- **IntegrityError** catches UNIQUE constraint violations

---

**2. Mark Entry**

```python
def mark_entry(self, student_id: str, name: str, subject: str = None) -> Tuple[bool, str]:
    """Mark student entry. Returns (success, message)."""
    try:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            entry_time = now.strftime('%Y-%m-%dT%H:%M:%S')
            date = now.strftime('%Y-%m-%d')
            
            if subject is None:
                subject = self.get_active_subject()
            
            # Check if already inside
            cursor.execute(
                """
                SELECT id FROM entry_log
                WHERE student_id = ? AND date = ? AND subject = ? AND status = 'INSIDE'
                """,
                (student_id, date, subject)
            )
            
            if cursor.fetchone():
                return False, "Already marked entry for this subject today"
            
            # Insert entry
            cursor.execute(
                """
                INSERT INTO entry_log (student_id, name, entry_time, date, subject, status)
                VALUES (?, ?, ?, ?, ?, 'INSIDE')
                """,
                (student_id, name, entry_time, date, subject)
            )
            
            return True, "Entry marked successfully"
            
    except Exception as e:
        logger.error(f"Failed to mark entry: {e}")
        return False, str(e)
```

**Logic Flow:**
1. Get current timestamp
2. Check for existing INSIDE status (prevent duplicates)
3. Insert new entry with status='INSIDE'
4. Return success/failure

---

**3. Mark Exit**

```python
def mark_exit(self, student_id: str, name: str, subject: str = None) -> Tuple[bool, str, Optional[int]]:
    """
    Mark student exit and calculate duration.
    Returns (success, message, duration_seconds).
    """
    try:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            exit_time = now.strftime('%Y-%m-%dT%H:%M:%S')
            date = now.strftime('%Y-%m-%d')
            
            if subject is None:
                subject = self.get_active_subject()
            
            # Find matching entry
            cursor.execute(
                """
                SELECT id, entry_time FROM entry_log
                WHERE student_id = ? AND date = ? AND subject = ? AND status = 'INSIDE'
                ORDER BY entry_time DESC LIMIT 1
                """,
                (student_id, date, subject)
            )
            
            row = cursor.fetchone()
            if not row:
                return False, "No entry found for today", None
            
            entry_id, entry_time_str = row
            
            # Calculate duration
            entry_dt = datetime.fromisoformat(entry_time_str)
            exit_dt = datetime.fromisoformat(exit_time)
            duration = int((exit_dt - entry_dt).total_seconds())
            
            if duration < 0:
                return False, "Invalid exit time (before entry)", None
            
            # Insert exit record
            cursor.execute(
                """
                INSERT INTO exit_log (student_id, name, entry_id, exit_time, date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, name, entry_id, exit_time, date)
            )
            
            # Update entry status
            cursor.execute(
                """
                UPDATE entry_log SET status = 'EXITED' WHERE id = ?
                """,
                (entry_id,)
            )
            
            # Insert attendance record
            status = 'PRESENT' if duration >= 1800 else 'ABSENT'  # 30 min minimum
            
            cursor.execute(
                """
                INSERT INTO attendance 
                (student_id, name, entry_time, exit_time, duration, status, date, subject)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, name, entry_time_str, exit_time, duration, status, date, subject)
            )
            
            return True, "Exit marked successfully", duration
            
    except Exception as e:
        logger.error(f"Failed to mark exit: {e}")
        return False, str(e), None
```

**Transaction Flow:**
1. Find active entry (status='INSIDE')
2. Calculate duration (exit - entry)
3. Insert into exit_log
4. Update entry_log status to 'EXITED'
5. Insert calculated record into attendance
6. All or nothing (transaction safety)

---

**4. Get Attendance Report**

```python
def get_attendance_report(self, date_from: str = None, date_to: str = None, 
                         subject: str = None) -> List[Tuple]:
    """
    Get attendance records for date range.
    Returns: [(id, student_id, name, entry_time, exit_time, duration, status, date, subject), ...]
    """
    with self.get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM attendance WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        
        if subject:
            query += " AND subject = ?"
            params.append(subject)
        
        query += " ORDER BY date DESC, entry_time DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
```

**Key Features:**
- **Dynamic WHERE clause** building
- **Parameterized queries** (safe from injection)
- **Ordered results** (newest first)

---

**5. Get All Students**

```python
def get_all_students(self) -> List[Tuple]:
    """
    Get all registered students.
    Returns: [(student_id, name, roll_number, registered_date), ...]
    """
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT student_id, name, roll_number, registered_date
            FROM students
            ORDER BY name ASC
            """
        )
        return cursor.fetchall()
```

**Important**: Returns **tuples**, not dictionaries!
```python
students = db.get_all_students()
for s in students:
    student_id = s[0]   # NOT s["student_id"]
    name = s[1]         # NOT s["name"]
    roll = s[2]         # NOT s["roll_number"]
```

To get dictionaries, set row_factory:
```python
conn.row_factory = sqlite3.Row
cursor.execute("SELECT * FROM students")
row = cursor.fetchone()
student_id = row["student_id"]  # Now works!
```

---

## 🚀 Indexing Strategy

### Why Indexes Matter

**Without Index:**
```sql
SELECT * FROM attendance WHERE date = '2026-03-03';
-- Scans ALL rows (O(n) - slow for 10,000+ records)
```

**With Index:**
```sql
-- Same query, but uses index
-- Binary search (O(log n) - fast even for millions of records)
```

### Our Indexes

**1. Entry Log Indexes**

```sql
-- Composite index for common query pattern
CREATE INDEX idx_entry_log_student_date_status
ON entry_log (student_id, date, status)
```

**Optimizes:**
```sql
SELECT * FROM entry_log 
WHERE student_id = ? AND date = ? AND status = 'INSIDE'
-- Common pattern: check if student already entered today
```

**Why This Order?**
- Most selective first (student_id narrows down most)
- Then date (further filters)
- Then status (final filter)

---

**2. Prevent Duplicate Active Sessions**

```sql
CREATE UNIQUE INDEX idx_entry_unique_inside_per_subject
ON entry_log (student_id, date, subject)
WHERE status = 'INSIDE'
```

**What This Does:**
- Allows: Multiple entries per day (different subjects)
- Allows: Multiple 'EXITED' entries
- Prevents: Two 'INSIDE' entries for same student+date+subject

**Partial Index Benefits:**
- Only indexes 'INSIDE' rows (saves space)
- Enforces business rule at DB level
- Faster than application-level checks

---

**3. Attendance Report Indexes**

```sql
-- Fast date range queries
CREATE INDEX idx_attendance_date
ON attendance (date DESC)

-- Fast student history
CREATE INDEX idx_attendance_student_date
ON attendance (student_id, date DESC)

-- Fast subject reports
CREATE INDEX idx_attendance_subject_date
ON attendance (subject, date DESC)
```

**Optimizes:**
```sql
-- Daily report
SELECT * FROM attendance WHERE date = '2026-03-03'
-- Uses: idx_attendance_date

-- Student history
SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC
-- Uses: idx_attendance_student_date

-- Subject report
SELECT * FROM attendance WHERE subject = 'Data Science' AND date >= ?
-- Uses: idx_attendance_subject_date
```

---

**4. Unique Attendance Session**

```sql
CREATE UNIQUE INDEX idx_attendance_unique_session
ON attendance (student_id, date, entry_time)
```

**Prevents:**
- Duplicate attendance records
- Same student counted twice for same session

---

## 🔧 Connection Management

### Thread Safety

**Problem**: SQLite connections aren't thread-safe by default

**Solution**: `check_same_thread=False` + thread-local connections

```python
import threading

class ThreadSafeDB:
    def __init__(self):
        self._local = threading.local()
    
    def get_connection(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(db_path, check_same_thread=False)
        return self._local.conn
```

**Our Approach**: Single connection per request (context manager ensures cleanup)

---

### Handling "Database is Locked"

**Causes:**
1. Long-running transaction
2. Multiple concurrent writes
3. Connection not closed properly

**Solutions:**

**1. Increase Timeout**
```python
conn = sqlite3.connect(db_path, timeout=30.0)  # Wait 30s
```

**2. Enable WAL Mode**
```python
conn.execute("PRAGMA journal_mode = WAL")
# Readers don't block writers
```

**3. Always Use Context Managers**
```python
# BAD - might leak connection
conn = db.get_connection()
cursor.execute("SELECT ...")
conn.close()  # Might not run if exception!

# GOOD - always closes
with db.get_connection() as conn:
    cursor.execute("SELECT ...")
# Auto-closes even on exception
```

---

## 🛡️ Data Integrity & Constraints

### 1. Primary Keys

```sql
student_id TEXT PRIMARY KEY
-- Same as:
student_id TEXT NOT NULL UNIQUE
```

**Guarantees:**
- Uniqueness (no duplicates)
- Not null (must have value)
- Indexed automatically (fast lookups)

---

### 2. Foreign Keys

```sql
FOREIGN KEY (student_id) REFERENCES students(student_id)
```

**Prevents:**
```sql
-- This will FAIL if student doesn't exist
INSERT INTO entry_log (student_id, ...) VALUES ('nonexistent_id', ...);
-- Error: FOREIGN KEY constraint failed
```

**Cascading Actions** (not used in our system, but available):
```sql
FOREIGN KEY (student_id) REFERENCES students(student_id)
ON DELETE CASCADE  -- Delete student → delete all their attendance
ON UPDATE CASCADE  -- Update student_id → update all references
```

---

### 3. UNIQUE Constraints

```sql
roll_number TEXT UNIQUE NOT NULL
```

**Prevents:**
```sql
INSERT INTO students (..., roll_number) VALUES (..., '2301105225');  -- OK
INSERT INTO students (..., roll_number) VALUES (..., '2301105225');  -- FAILS
-- Error: UNIQUE constraint failed: students.roll_number
```

---

### 4. CHECK Constraints

```sql
duration INTEGER NOT NULL CHECK(duration >= 0)
status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT'))
```

**Enforces Business Rules:**
```sql
-- This will FAIL
INSERT INTO attendance (duration, status, ...) VALUES (-100, 'INVALID', ...);
-- Error: CHECK constraint failed
```

---

### 5. NOT NULL Constraints

```sql
name TEXT NOT NULL
```

**Prevents:**
```sql
INSERT INTO students (student_id, name, ...) VALUES ('id123', NULL, ...);
-- Error: NOT NULL constraint failed: students.name
```

---

## ⚡ Performance Optimization

### Query Optimization

**1. Use EXPLAIN QUERY PLAN**

```sql
EXPLAIN QUERY PLAN
SELECT * FROM attendance WHERE date > '2026-03-01' AND subject = 'Data Science';
```

**Output:**
```
SEARCH TABLE attendance USING INDEX idx_attendance_subject_date (subject=? AND date>?)
```

**Good**: Uses index  
**Bad**: `SCAN TABLE` (full table scan)

---

**2. Avoid SELECT ***

```sql
-- BAD - retrieves all columns
SELECT * FROM attendance;

-- GOOD - only needed columns
SELECT student_id, name, date FROM attendance;
```

**Why?**
- Less data transferred
- Less memory used
- Faster parsing

---

**3. Use LIMIT for Large Results**

```sql
-- Don't load 10,000 rows at once
SELECT * FROM attendance ORDER BY date DESC LIMIT 50;
```

---

**4. Batch Inserts**

```python
# BAD - 100 separate transactions
for student in students:
    db.register_student(student)

# GOOD - single transaction
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?)",
        [(s.id, s.name, s.roll, s.date) for s in students]
    )
```

**Speed Improvement**: 100x faster!

---

### Cache Settings

```python
# Default: 2000 pages * 1KB = 2MB cache
PRAGMA cache_size = -64000  # 64MB cache

# Store temp tables in RAM (faster)
PRAGMA temp_store = MEMORY
```

---

## 🐛 Troubleshooting & Best Practices

### Common Errors

**1. "database is locked"**

**Cause**: Another write operation is active

**Solutions:**
```python
# Increase timeout
conn = sqlite3.connect(db_path, timeout=30.0)

# Check for unclosed connections
# ALWAYS use context managers

# Enable WAL mode
conn.execute("PRAGMA journal_mode = WAL")
```

---

**2. "UNIQUE constraint failed"**

**Cause**: Trying to insert duplicate unique value

**Solution:**
```python
try:
    cursor.execute("INSERT INTO students ...")
except sqlite3.IntegrityError:
    print("Student already registered")
    # Handle duplicate
```

---

**3. "FOREIGN KEY constraint failed"**

**Cause**: Referenced row doesn't exist

**Solution:**
```python
# Check if student exists first
cursor.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,))
if not cursor.fetchone():
    raise ValueError("Student not registered")

# Then insert
cursor.execute("INSERT INTO entry_log ...")
```

---

**4. "no such table: students"**

**Cause**: Database not initialized

**Solution:**
```python
db = DatabaseManager()  # This calls create_tables()
```

---

### Best Practices

**1. Always Parameterize Queries**

```python
# BAD - SQL injection vulnerability
cursor.execute(f"SELECT * FROM students WHERE name = '{name}'")

# GOOD - safe from injection
cursor.execute("SELECT * FROM students WHERE name = ?", (name,))
```

---

**2. Use Transactions for Multi-Step Operations**

```python
try:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Step 1: Insert entry
        cursor.execute("INSERT INTO entry_log ...")
        
        # Step 2: Update status
        cursor.execute("UPDATE students SET status = ...")
        
        # Both commit together (or both rollback)
except Exception:
    # Automatic rollback on error
    pass
```

---

**3. Close Connections Properly**

```python
# Use context managers
with db.get_connection() as conn:
    # Your code
    pass
# Auto-closes here
```

---

**4. Regular Backups**

```python
import shutil
from datetime import datetime

def backup_database():
    db_path = "data/database/attendance.db"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"backups/attendance_{timestamp}.db"
    
    shutil.copy2(db_path, backup_path)
    return backup_path
```

---

**5. Vacuum Database Periodically**

```python
# Reclaim unused space, defragment
def optimize_database():
    with db.get_connection() as conn:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
```

Run monthly or after large delete operations.

---

## ❓ FAQs for Database Developers

**Q1: Why TEXT for dates instead of INTEGER (Unix timestamp)?**

A: Human readability. ISO format is easily readable and sortable:
```sql
-- Easy to read
'2026-03-03T10:30:00'

-- Hard to read
1709457000
```

For performance-critical apps, Unix timestamps are faster, but our system prioritizes clarity.

---

**Q2: Should I use row_factory for dictionary access?**

A: **For backend code**: No, tuples are faster  
**For API responses**: Convert to dicts in application layer

```python
# Efficient
students = cursor.fetchall()  # Returns tuples
result = [{"id": s[0], "name": s[1]} for s in students]  # Convert once

# Less efficient
conn.row_factory = sqlite3.Row  # Overhead for every query
```

---

**Q3: How do I migrate the database schema?**

A: Add migration logic:

```python
def migrate_schema():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check current version
        try:
            cursor.execute("SELECT value FROM system_settings WHERE key = 'schema_version'")
            version = cursor.fetchone()[0]
        except:
            version = "1.0"
        
        # Apply migrations
        if version == "1.0":
            # Add email column to students
            cursor.execute("ALTER TABLE students ADD COLUMN email TEXT")
            cursor.execute("UPDATE system_settings SET value = '1.1' WHERE key = 'schema_version'")
```

---

**Q4: Can I use SQLite with Async/Await?**

A: SQLite is synchronous, but you can use thread pools:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=5)

async def async_query():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        lambda: db.get_all_students()
    )
    return result
```

Or use `aiosqlite` library:
```python
import aiosqlite

async with aiosqlite.connect(db_path) as conn:
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT * FROM students")
        rows = await cursor.fetchall()
```

---

**Q5: How do I handle time zones?**

A: Store UTC, convert on display:

```python
from datetime import datetime, timezone

# Store in UTC
now_utc = datetime.now(timezone.utc)
timestamp = now_utc.isoformat()

# Display in local time
dt = datetime.fromisoformat(timestamp)
local_time = dt.astimezone()  # Converts to system timezone
```

---

**Q6: What's the maximum database size?**

A: SQLite can handle **281 TB** (theoretical limit)  
Practical limit: **100 GB** for good performance  
Our system: ~**100 KB** to **10 MB** typical

---

**Q7: How do I query across multiple databases?**

A: Use ATTACH:

```python
conn.execute("ATTACH DATABASE 'backup.db' AS backup")
conn.execute("SELECT * FROM main.students UNION SELECT * FROM backup.students")
```

---

**Q8: Should I use triggers?**

A: For automated actions, yes:

```sql
-- Auto-update timestamp
CREATE TRIGGER update_timestamp
AFTER UPDATE ON students
FOR EACH ROW
BEGIN
    UPDATE students SET updated_at = datetime('now') WHERE student_id = NEW.student_id;
END;
```

Our system doesn't use triggers (prefer explicit Python logic for clarity).

---

**Q9: How do I debug slow queries?**

A:
```python
import time

start = time.time()
cursor.execute("SELECT * FROM attendance WHERE ...")
duration = time.time() - start

if duration > 0.1:  # Slower than 100ms
    print(f"SLOW QUERY: {duration:.3f}s")
```

Also check:
```sql
EXPLAIN QUERY PLAN SELECT ...;  -- See if index is used
```

---

**Q10: Can I use SQLite for production?**

A: **Yes**, if:
- ✅ Single server deployment
- ✅ Moderate write load (< 100 writes/sec)
- ✅ Embedded/local application

**No**, if:
- ❌ Multi-server (need PostgreSQL/MySQL)
- ❌ High concurrent writes (> 1000 writes/sec)
- ❌ Network database (SQLite is local only)

**Our attendance system**: Perfect fit for SQLite!

---

## 🎓 Advanced Topics

### Full-Text Search

```sql
-- Create FTS table
CREATE VIRTUAL TABLE students_fts USING fts5(student_id, name, roll_number);

-- Populate
INSERT INTO students_fts SELECT student_id, name, roll_number FROM students;

-- Fast text search
SELECT * FROM students_fts WHERE students_fts MATCH 'Kumar';
```

### JSON Support (SQLite 3.38+)

```sql
-- Store JSON
INSERT INTO system_settings (key, value) VALUES 
('config', '{"theme": "dark", "lang": "en"}');

-- Query JSON
SELECT json_extract(value, '$.theme') FROM system_settings WHERE key = 'config';
-- Returns: "dark"
```

### Window Functions

```sql
-- Rank students by attendance
SELECT 
    student_id,
    COUNT(*) as days_present,
    RANK() OVER (ORDER BY COUNT(*) DESC) as rank
FROM attendance
WHERE status = 'PRESENT'
GROUP BY student_id;
```

---

## 📚 References

**Official Documentation:**
- SQLite Docs: https://www.sqlite.org/docs.html
- Python sqlite3: https://docs.python.org/3/library/sqlite3.html

**Performance Tuning:**
- https://www.sqlite.org/pragma.html
- https://www.sqlite.org/queryplanner.html

**Best Practices:**
- https://www.sqlite.org/bestpractice.html

---

**Database Location**: `data/database/attendance.db`  
**Backup Strategy**: Copy file to backup location  
**View Database**: Use [DB Browser for SQLite](https://sqlitebrowser.org/)
