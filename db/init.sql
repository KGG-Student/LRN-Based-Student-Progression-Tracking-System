USE mydb;

CREATE TABLE students (
    lrn VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE student_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lrn VARCHAR(20),
    school_year VARCHAR(20),
    grade_level INT,
    gender VARCHAR(10),
    status VARCHAR(50),
    FOREIGN KEY (lrn) REFERENCES students(lrn)
);