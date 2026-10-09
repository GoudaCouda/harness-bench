CREATE TABLE transcript(student_id TEXT,course TEXT,term TEXT,grade TEXT,source TEXT);
CREATE TABLE equivalencies(source_course TEXT,target_course TEXT,valid_from TEXT,valid_to TEXT);
CREATE TABLE substitutions(id TEXT,source_course TEXT,requirement TEXT,status TEXT);
CREATE TABLE prerequisites(course TEXT,prerequisite TEXT);
INSERT INTO transcript VALUES ('S-42','CS-101','2025-FALL','A','institution'),('S-42','CS-201','2026-SPRING','B','institution'),('S-42','MATH-101','2025-FALL','B','institution'),('S-42','STAT-210','2026-SPRING','A','transfer'),('S-42','HUM-110','2026-SPRING','A','institution'),('S-42','CALC-A','2024-SPRING','B','transfer');
INSERT INTO equivalencies VALUES ('STAT-210','STAT-200','2026-01-01','2027-12-31'),('CALC-A','MATH-101','2023-01-01','2024-12-31');
INSERT INTO substitutions VALUES ('SUB-7','HUM-110','ethics','approved');
INSERT INTO prerequisites VALUES ('CS-201','CS-101'),('CS-301','CS-201'),('CS-301','STAT-200'),('CS-399','CS-301');
