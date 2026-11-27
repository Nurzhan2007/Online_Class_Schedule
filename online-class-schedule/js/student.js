/*
 KBTU Online Class Schedule
 Student dashboard page: profile, GPA, degree progress, courses.

 Uses (already in the project):
   i18n.js  -> TRANSLATIONS, t(), loc(), esc()
   api.js   -> CourseAPI, DAY_ORDER
   app.js   -> app, currentUser, header(), navigate()

 Load this file after api.js (see index.html).

 DATA NOTE
 The backend has no grades / GPA / faculty yet, so the academic data below is
 DEMO data. StudentAPI is the only place that knows where the data comes from.
 When the backend gets e.g. GET /api/me/profile and GET /api/me/grades,
 only StudentAPI.get() has to change - the page itself stays the same.
*/

// =================================
// TRANSLATIONS (added to the existing ones)
// =================================
Object.assign(TRANSLATIONS.en, {
    "nav.student": "Student Dashboard",

    "sd.title": "Student Dashboard",
    "sd.subtitle": "Your personal information and academic progress",
    "sd.demoNote": "Demo data: grades and academic information will come from the university system.",
    "sd.notStudent": "Academic data (GPA, progress) is available for student accounts only.",

    "sd.profile": "Student information",
    "sd.studentId": "Student ID",
    "sd.email": "Email",
    "sd.role": "Role",
    "sd.faculty": "Faculty",
    "sd.department": "Department",
    "sd.position": "Position",
    "sd.specialty": "Specialty",
    "sd.degree": "Degree",
    "sd.studyYear": "Year of study",
    "sd.admission": "Admission year",
    "sd.status": "Status",
    "sd.notSet": "Not specified",
    "sd.degree.bachelor": "Bachelor",
    "sd.status.active": "Active",
    "sd.yearN": "Year {n}",

    "sd.gpa": "Cumulative GPA",
    "sd.gpaScale": "out of 4.0",
    "sd.creditsEarned": "Credits earned",
    "sd.creditsNow": "Credits in progress",
    "sd.coursesNow": "Courses this semester",

    "sd.progress.title": "Degree progress",
    "sd.progress.text": "{done} of {total} credits completed",
    "sd.progress.legendDone": "Completed",
    "sd.progress.legendNow": "In progress",
    "sd.progress.legendLeft": "Remaining",
    "sd.progress.years": "Years of study",

    "sd.gpaBySemester": "GPA by semester",
    "sd.current.title": "Current semester courses",
    "sd.current.empty": "You have no registered courses this semester.",
    "sd.completed.title": "Completed courses",
    "sd.completed.empty": "No completed courses yet.",

    "sd.col.code": "Code",
    "sd.col.course": "Course",
    "sd.col.instructor": "Instructor",
    "sd.col.schedule": "Schedule",
    "sd.col.credits": "Credits",
    "sd.col.grade": "Grade",
    "sd.col.points": "Points",
    "sd.col.status": "Status",
    "sd.inProgress": "In progress",

    "sd.term.fall": "Fall",
    "sd.term.spring": "Spring",
    "sd.semesterSummary": "GPA {gpa} · {credits} credits"
});

Object.assign(TRANSLATIONS.ru, {
    "nav.student": "Кабинет студента",

    "sd.title": "Кабинет студента",
    "sd.subtitle": "Ваши личные данные и академическая успеваемость",
    "sd.demoNote": "Демо-данные: оценки и академическая информация будут поступать из университетской системы.",
    "sd.notStudent": "Академические данные (GPA, прогресс) доступны только студенческим аккаунтам.",

    "sd.profile": "Информация о студенте",
    "sd.studentId": "Студенческий ID",
    "sd.email": "Email",
    "sd.role": "Роль",
    "sd.faculty": "Факультет",
    "sd.department": "Кафедра / отдел",
    "sd.position": "Должность",
    "sd.specialty": "Специальность",
    "sd.degree": "Уровень обучения",
    "sd.studyYear": "Курс",
    "sd.admission": "Год поступления",
    "sd.status": "Статус",
    "sd.notSet": "Не указано",
    "sd.degree.bachelor": "Бакалавриат",
    "sd.status.active": "Обучается",
    "sd.yearN": "{n} курс",

    "sd.gpa": "Общий GPA",
    "sd.gpaScale": "из 4.0",
    "sd.creditsEarned": "Получено кредитов",
    "sd.creditsNow": "Кредиты в процессе",
    "sd.coursesNow": "Курсов в этом семестре",

    "sd.progress.title": "Прогресс обучения",
    "sd.progress.text": "Пройдено {done} из {total} кредитов",
    "sd.progress.legendDone": "Пройдено",
    "sd.progress.legendNow": "В процессе",
    "sd.progress.legendLeft": "Осталось",
    "sd.progress.years": "Годы обучения",

    "sd.gpaBySemester": "GPA по семестрам",
    "sd.current.title": "Курсы текущего семестра",
    "sd.current.empty": "В этом семестре вы не записаны ни на один курс.",
    "sd.completed.title": "Пройденные курсы",
    "sd.completed.empty": "Пройденных курсов пока нет.",

    "sd.col.code": "Код",
    "sd.col.course": "Курс",
    "sd.col.instructor": "Преподаватель",
    "sd.col.schedule": "Расписание",
    "sd.col.credits": "Кредиты",
    "sd.col.grade": "Оценка",
    "sd.col.points": "Баллы",
    "sd.col.status": "Статус",
    "sd.inProgress": "Идёт",

    "sd.term.fall": "Осень",
    "sd.term.spring": "Весна",
    "sd.semesterSummary": "GPA {gpa} · {credits} кредитов"
});

Object.assign(TRANSLATIONS.kk, {
    "nav.student": "Студент кабинеті",

    "sd.title": "Студент кабинеті",
    "sd.subtitle": "Жеке мәліметтеріңіз бен оқу үлгерімі",
    "sd.demoNote": "Демо деректер: бағалар мен академиялық ақпарат университет жүйесінен келеді.",
    "sd.notStudent": "Академиялық деректер (GPA, прогресс) тек студент аккаунттарына қолжетімді.",

    "sd.profile": "Студент туралы ақпарат",
    "sd.studentId": "Студент ID",
    "sd.email": "Email",
    "sd.role": "Рөлі",
    "sd.faculty": "Факультет",
    "sd.department": "Кафедра / бөлім",
    "sd.position": "Лауазымы",
    "sd.specialty": "Мамандық",
    "sd.degree": "Оқу деңгейі",
    "sd.studyYear": "Курс",
    "sd.admission": "Түскен жылы",
    "sd.status": "Мәртебесі",
    "sd.notSet": "Көрсетілмеген",
    "sd.degree.bachelor": "Бакалавриат",
    "sd.status.active": "Оқиды",
    "sd.yearN": "{n}-курс",

    "sd.gpa": "Жалпы GPA",
    "sd.gpaScale": "4.0-ден",
    "sd.creditsEarned": "Жиналған кредиттер",
    "sd.creditsNow": "Орындалып жатқан кредиттер",
    "sd.coursesNow": "Осы семестрдегі курстар",

    "sd.progress.title": "Оқу прогресі",
    "sd.progress.text": "{total} кредиттің {done}-і аяқталды",
    "sd.progress.legendDone": "Аяқталған",
    "sd.progress.legendNow": "Орындалып жатыр",
    "sd.progress.legendLeft": "Қалғаны",
    "sd.progress.years": "Оқу жылдары",

    "sd.gpaBySemester": "Семестр бойынша GPA",
    "sd.current.title": "Ағымдағы семестр курстары",
    "sd.current.empty": "Осы семестрге ешбір курсқа тіркелмегенсіз.",
    "sd.completed.title": "Аяқталған курстар",
    "sd.completed.empty": "Аяқталған курстар әлі жоқ.",

    "sd.col.code": "Коды",
    "sd.col.course": "Курс",
    "sd.col.instructor": "Оқытушы",
    "sd.col.schedule": "Кесте",
    "sd.col.credits": "Кредит",
    "sd.col.grade": "Баға",
    "sd.col.points": "Ұпай",
    "sd.col.status": "Мәртебесі",
    "sd.inProgress": "Жүріп жатыр",

    "sd.term.fall": "Күзгі",
    "sd.term.spring": "Көктемгі",
    "sd.semesterSummary": "GPA {gpa} · {credits} кредит"
});

// =================================
// ACADEMIC SETTINGS
// =================================
const DEGREE_CREDITS = 130;   // credits needed for the degree (demo value)
const STUDY_YEARS = 4;

// 4.0 scale. GPA = sum(points * credits) / sum(credits)
const GRADE_POINTS = {
    "A": 4.0,
    "A-": 3.67,
    "B+": 3.33,
    "B": 3.0,
    "B-": 2.67,
    "C+": 2.33,
    "C": 2.0,
    "C-": 1.67,
    "D+": 1.33,
    "D": 1.0,
    "F": 0
};

// =================================
// DEMO DATA (key = e-mail of the user)
// =================================
function sdCourse(code, en, ru, kk, credits) {
    return { code: code, name: { en: en, ru: ru, kk: kk }, credits: credits };
}

// Study plan: 6 semesters x 5 courses (same for the demo students)
const DEMO_CURRICULUM = [
    [
        sdCourse("CSCI1101", "Programming Principles I", "Принципы программирования I", "Бағдарламалау принциптері I", 5),
        sdCourse("HIST1101", "History of Kazakhstan", "История Казахстана", "Қазақстан тарихы", 3),
        sdCourse("LANG1101", "Academic English I", "Академический английский I", "Академиялық ағылшын тілі I", 3),
        sdCourse("MATH1101", "Mathematical Analysis I", "Математический анализ I", "Математикалық талдау I", 5),
        sdCourse("PHED1101", "Physical Education I", "Физическая культура I", "Дене шынықтыру I", 2)
    ],
    [
        sdCourse("CSCI1102", "Programming Principles II", "Принципы программирования II", "Бағдарламалау принциптері II", 5),
        sdCourse("MATH1102", "Mathematical Analysis II", "Математический анализ II", "Математикалық талдау II", 5),
        sdCourse("LANG1102", "Academic English II", "Академический английский II", "Академиялық ағылшын тілі II", 3),
        sdCourse("PHIL1101", "Philosophy", "Философия", "Философия", 3),
        sdCourse("PHED1102", "Physical Education II", "Физическая культура II", "Дене шынықтыру II", 2)
    ],
    [
        sdCourse("CSCI2101", "Object-Oriented Programming", "Объектно-ориентированное программирование", "Объектіге бағытталған бағдарламалау", 5),
        sdCourse("MATH2101", "Probability Theory", "Теория вероятностей", "Ықтималдықтар теориясы", 4),
        sdCourse("CSCI2102", "Computer Architecture", "Архитектура компьютеров", "Компьютер архитектурасы", 4),
        sdCourse("LANG2101", "Professional Kazakh", "Профессиональный казахский язык", "Кәсіби қазақ тілі", 3),
        sdCourse("ECOL1101", "Ecology and Life Safety", "Экология и безопасность жизнедеятельности", "Экология және өмір қауіпсіздігі", 2)
    ],
    [
        sdCourse("CSCI2103", "Digital Logic Design", "Цифровая логика", "Цифрлық логика", 4),
        sdCourse("LANG2102", "Technical Writing", "Техническое письмо", "Техникалық жазу", 3),
        sdCourse("ECON1101", "Economics for Engineers", "Экономика для инженеров", "Инженерлерге арналған экономика", 3),
        sdCourse("CSCI2104", "Software Engineering Basics", "Основы программной инженерии", "Бағдарламалық инженерия негіздері", 5),
        sdCourse("CSCI2105", "Information Security Basics", "Основы информационной безопасности", "Ақпараттық қауіпсіздік негіздері", 3)
    ],
    [
        sdCourse("CSCI3101", "Databases", "Базы данных", "Деректер қорлары", 5),
        sdCourse("CSCI3102", "Operating Systems", "Операционные системы", "Операциялық жүйелер", 4),
        sdCourse("MATH3101", "Discrete Mathematics", "Дискретная математика", "Дискретті математика", 4),
        sdCourse("CSCI3103", "Computer Networks", "Компьютерные сети", "Компьютерлік желілер", 4),
        sdCourse("LANG3101", "Business English", "Деловой английский", "Іскерлік ағылшын тілі", 3)
    ],
    [
        sdCourse("CSCI3104", "Web Development", "Веб-разработка", "Веб-әзірлеу", 5),
        sdCourse("CSCI3105", "Algorithms and Complexity", "Алгоритмы и сложность", "Алгоритмдер және күрделілік", 5),
        sdCourse("CSCI3106", "Human-Computer Interaction", "Взаимодействие человека и компьютера", "Адам мен компьютер өзара әрекеті", 3),
        sdCourse("STAT3101", "Statistics for Data Analysis", "Статистика для анализа данных", "Деректерді талдауға арналған статистика", 4),
        sdCourse("ECON3101", "Entrepreneurship", "Предпринимательство", "Кәсіпкерлік", 3)
    ]
];

// Builds the transcript: grades[i] = list of grades of semester i (same order as the curriculum).
// Semester 0 is Fall of the admission year, 1 is Spring of the next year, and so on.
function sdTranscript(admission, grades) {
    return grades.map((row, i) => ({
        year: admission + Math.floor(i / 2) + (i % 2),
        term: i % 2 === 0 ? "fall" : "spring",
        courses: DEMO_CURRICULUM[i].map((c, k) => ({ ...c, grade: row[k] }))
    }));
}

const SD_FACULTY_IT = {
    en: "School of Information Technology and Engineering",
    ru: "Школа информационных технологий и инженерии",
    kk: "Ақпараттық технологиялар және инженерия мектебі"
};
const SD_SPEC_IS = { en: "Information Systems", ru: "Информационные системы", kk: "Ақпараттық жүйелер" };
const SD_SPEC_SE = { en: "Software Engineering", ru: "Программная инженерия", kk: "Бағдарламалық инженерия" };

function sdStudent(specialty, admission, year, grades) {
    return {
        profile: {
            faculty: SD_FACULTY_IT,
            specialty: specialty,
            degree: "bachelor",
            admission: admission,
            year: year,
            status: "active"
        },
        semesters: sdTranscript(admission, grades)
    };
}

const DEMO_ACADEMIC = {

    // 3rd year, Information Systems: GPA 3.54 (checked by hand)
    "student@kbtu.kz": sdStudent(SD_SPEC_IS, 2024, 3, [
        ["A-", "A", "B+", "B", "A"],
        ["A", "B+", "A-", "B", "A"],
        ["A", "B+", "B", "A-", "A"],
        ["B+", "A", "B", "A-", "B+"]
    ]),

    // 4th year, very strong student
    "a.sadvakassova@kbtu.kz": sdStudent(SD_SPEC_IS, 2023, 4, [
        ["A", "A", "A-", "A", "A"],
        ["A", "A-", "A", "A", "A"],
        ["A", "A", "A-", "A", "A"],
        ["A-", "A", "A", "A", "A-"],
        ["A", "A-", "A", "B+", "A"],
        ["A", "A", "A-", "A", "A"]
    ]),

    // 3rd year, a weaker semester with a retake (F)
    "m.zhaksybekova@kbtu.kz": sdStudent(SD_SPEC_IS, 2024, 3, [
        ["B", "A-", "B", "C+", "A"],
        ["B-", "C", "B", "B", "A-"],
        ["C+", "F", "C", "B", "A"],
        ["B", "B+", "C+", "B-", "B"]
    ]),

    // 3rd year, Software Engineering, average student
    "a.kim@kbtu.kz": sdStudent(SD_SPEC_SE, 2024, 3, [
        ["B+", "B", "B+", "B", "A"],
        ["B", "B+", "B", "B-", "A"],
        ["B+", "B", "B+", "B", "A-"],
        ["B", "B+", "B", "B+", "B"]
    ]),

    // 2nd year
    "d.omarov@kbtu.kz": sdStudent(SD_SPEC_SE, 2025, 2, [
        ["A-", "A", "B+", "A-", "A"],
        ["A", "B+", "A", "A-", "A"]
    ]),

    // 1st year: no finished semesters yet (empty transcript state)
    "a.tleuov@kbtu.kz": sdStudent(SD_SPEC_SE, 2026, 1, [])
};

// Teachers and admin: no grades, but a detailed profile
const DEMO_STAFF = {
    "teacher@kbtu.kz": {
        faculty: SD_FACULTY_IT,
        department: { en: "Department of Computer Science", ru: "Кафедра компьютерных наук", kk: "Информатика кафедрасы" },
        position: { en: "Senior Lecturer", ru: "Старший преподаватель", kk: "Аға оқытушы" }
    },
    "timur.akhmetov@kbtu.kz": {
        faculty: SD_FACULTY_IT,
        department: { en: "Department of Computer Science", ru: "Кафедра компьютерных наук", kk: "Информатика кафедрасы" },
        position: { en: "Associate Professor", ru: "Ассоциированный профессор", kk: "Қауымдастырылған профессор" }
    },
    "olga.ivanova@kbtu.kz": {
        faculty: SD_FACULTY_IT,
        department: { en: "Department of Information Systems", ru: "Кафедра информационных систем", kk: "Ақпараттық жүйелер кафедрасы" },
        position: { en: "Lecturer", ru: "Преподаватель", kk: "Оқытушы" }
    },
    "admin@kbtu.kz": {
        faculty: null,
        department: { en: "Registrar's Office", ru: "Офис регистратора", kk: "Тіркеуші кеңсесі" },
        position: { en: "System Administrator", ru: "Системный администратор", kk: "Жүйе әкімшісі" }
    }
};

// =================================
// HELPERS
// =================================
function gradePointsOf(grade) {
    return GRADE_POINTS[grade] !== undefined ? GRADE_POINTS[grade] : 0;
}

function sumCredits(courses) {
    return courses.reduce((total, c) => total + c.credits, 0);
}

// Weighted GPA; null when there is nothing to count
function calcGpa(courses) {
    const credits = sumCredits(courses);

    if (!credits) {
        return null;
    }

    const points = courses.reduce(
        (total, c) => total + gradePointsOf(c.grade) * c.credits,
        0
    );

    return points / credits;
}

function fmtGpa(value) {
    return value === null ? "—" : value.toFixed(2);
}

function termLabel(semester) {
    return t("sd.term." + semester.term) + " " + semester.year;
}

function initials(name) {
    return String(name)
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map(word => word.charAt(0))
        .join("")
        .toUpperCase();
}

// Student IDs look like 24B031586: the first two digits are the admission year
// (this is an assumption about the ID format; used only when there is no demo profile)
function deriveFromStudentId(studentId) {
    const match = /^(\d{2})([A-Za-z])/.exec(String(studentId || ""));

    if (!match) {
        return null;
    }

    const admission = 2000 + Number(match[1]);
    const now = new Date();

    // the academic year starts in September
    const year = now.getFullYear() - admission + (now.getMonth() >= 8 ? 1 : 0);

    if (year < 1 || year > STUDY_YEARS) {
        return null;
    }

    return {
        admission: admission,
        year: year,
        degree: match[2].toUpperCase() === "B" ? "bachelor" : null
    };
}

function sdTime(c) {
    return c.start + " - " + c.end;
}

function sdRoom(c) {
    return t("room." + c.room.kind) + " " + c.room.no;
}

// =================================
// DATA LAYER
// =================================
const StudentAPI = {

    // Profile and transcript of the user
    get(user) {
        const demo = DEMO_ACADEMIC[String(user.email).toLowerCase()];

        if (demo) {
            return { profile: demo.profile, semesters: demo.semesters };
        }

        const derived = deriveFromStudentId(user.studentId) || {};

        return {
            profile: {
                faculty: null,
                specialty: null,
                degree: derived.degree || null,
                admission: derived.admission || null,
                year: derived.year || null,
                status: "active"
            },
            semesters: []
        };
    },

    // Courses the student is registered for now
    currentCourses(email) {
        return CourseAPI.getRegisteredIds(email)
            .map(id => {
                const course = CourseAPI.getById(id);

                return course
                    ? { ...course, ...CourseAPI.getSection(email, id) }
                    : null;
            })
            .filter(Boolean)
            .sort((a, b) =>
                DAY_ORDER.indexOf(a.day) - DAY_ORDER.indexOf(b.day) ||
                a.start.localeCompare(b.start)
            );
    },

    // Everything the page needs
    summary(user) {
        const data = this.get(user);
        const finished = data.semesters.reduce(
            (all, s) => all.concat(s.courses), []
        );
        const current = this.currentCourses(user.email);

        return {
            profile: data.profile,
            current: current,
            gpa: calcGpa(finished),
            earned: sumCredits(finished.filter(c => c.grade !== "F")),
            inProgress: sumCredits(current),
            semesters: data.semesters.map(s => ({
                ...s,
                gpa: calcGpa(s.courses),
                credits: sumCredits(s.courses)
            })),
            total: DEGREE_CREDITS
        };
    }
};

// =================================
// PAGE PARTS
// =================================
function sdProfileCard(user, info, isStudent) {

    const p = info.profile;
    const role = user.role || "student";

    const notSet = t("sd.notSet");

    const rows = [
        [t("sd.studentId"), user.studentId ? esc(user.studentId) : notSet],
        [t("sd.email"), esc(user.email)]
    ];

    if (isStudent) {
        rows.push(
            [t("sd.faculty"), p.faculty ? esc(loc(p.faculty)) : notSet],
            [t("sd.specialty"), p.specialty ? esc(loc(p.specialty)) : notSet],
            [t("sd.degree"), p.degree ? t("sd.degree." + p.degree) : notSet],
            [t("sd.studyYear"), p.year ? t("sd.yearN", { n: p.year }) : notSet],
            [t("sd.admission"), p.admission ? p.admission : notSet],
            [t("sd.status"), t("sd.status." + p.status)]
        );
    } else {
        const staff = DEMO_STAFF[String(user.email).toLowerCase()];

        rows.push([t("sd.role"), esc(t("role." + role))]);

        if (staff) {
            rows.push(
                [t("sd.faculty"), staff.faculty ? esc(loc(staff.faculty)) : notSet],
                [t("sd.department"), esc(loc(staff.department))],
                [t("sd.position"), esc(loc(staff.position))]
            );
        }
    }

    return `
        <section class="card sd-profile">

            <div class="sd-profile-head">

                <div class="sd-avatar" aria-hidden="true">
                    ${esc(initials(user.name))}
                </div>

                <div>
                    <div class="sd-name">${esc(user.name)}</div>

                    <span class="role-label sd-role">
                        ${esc(t("role." + role).toUpperCase())}
                    </span>
                </div>

            </div>

            <dl class="sd-fields">

                ${rows.map(row => `
                    <dt>${row[0]}</dt>
                    <dd>${row[1]}</dd>
                `).join("")}

            </dl>

        </section>
    `;
}

function sdStats(info) {

    return `
        <div class="sd-stats">

            <div class="card">
                <p>${t("sd.gpa")}</p>
                <div class="stat-number">${fmtGpa(info.gpa)}</div>
                <span class="badge">${t("sd.gpaScale")}</span>
            </div>

            <div class="card">
                <p>${t("sd.creditsEarned")}</p>
                <div class="stat-number">${info.earned}</div>
                <span class="badge">/ ${info.total}</span>
            </div>

            <div class="card">
                <p>${t("sd.creditsNow")}</p>
                <div class="stat-number">${info.inProgress}</div>
                <span class="badge">${t("sd.inProgress")}</span>
            </div>

            <div class="card">
                <p>${t("sd.coursesNow")}</p>
                <div class="stat-number">${info.current.length}</div>
                <span class="badge">${t("dash.semester")}</span>
            </div>

        </div>
    `;
}

function sdProgress(info) {

    const done = Math.min(100, info.earned / info.total * 100);
    const now = Math.min(100 - done, info.inProgress / info.total * 100);
    const left = Math.max(0, info.total - info.earned - info.inProgress);

    const year = info.profile.year;

    const steps = [];

    for (let n = 1; n <= STUDY_YEARS; n++) {

        const state = year && n < year ? "done" : (year === n ? "current" : "");

        steps.push(`
            <div class="sd-step ${state}">
                ${t("sd.yearN", { n: n })}
            </div>
        `);
    }

    return `
        <section class="card">

            <h2>${t("sd.progress.title")}</h2>

            <p class="subtitle" style="margin:8px 0 0">
                ${t("sd.progress.text", { done: info.earned, total: info.total })}
                (${Math.round(done)}%)
            </p>

            <div class="sd-progress"
                role="progressbar"
                aria-valuemin="0"
                aria-valuemax="${info.total}"
                aria-valuenow="${info.earned}">

                <span class="sd-progress-done" style="width:${done}%"></span>
                <span class="sd-progress-now" style="width:${now}%"></span>

            </div>

            <div class="sd-legend">
                <span><i class="sd-dot done"></i>${t("sd.progress.legendDone")}: ${info.earned}</span>
                <span><i class="sd-dot now"></i>${t("sd.progress.legendNow")}: ${info.inProgress}</span>
                <span><i class="sd-dot left"></i>${t("sd.progress.legendLeft")}: ${left}</span>
            </div>

            <h3 class="sd-sub">${t("sd.progress.years")}</h3>

            <div class="sd-steps">${steps.join("")}</div>

        </section>
    `;
}

function sdGpaChart(info) {

    if (info.semesters.length === 0) {
        return "";
    }

    return `
        <section class="card">

            <h2>${t("sd.gpaBySemester")}</h2>

            <div class="sd-chart">

                ${info.semesters.map(s => `
                    <div class="sd-col"
                        title="${esc(termLabel(s))}: ${fmtGpa(s.gpa)}">

                        <span class="sd-col-val">${fmtGpa(s.gpa)}</span>

                        <div class="sd-col-track">
                            <div class="sd-col-fill"
                                style="height:${Math.round((s.gpa || 0) / 4 * 100)}%">
                            </div>
                        </div>

                        <span class="sd-col-label">${esc(termLabel(s))}</span>

                    </div>
                `).join("")}

            </div>

        </section>
    `;
}

function sdCurrentCourses(info) {

    if (info.current.length === 0) {

        return `
            <section class="card">

                <h2>${t("sd.current.title")}</h2>

                <div class="empty">
                    ${t("sd.current.empty")}
                    <br>
                    <button class="btn" onclick="navigate('courses')">
                        ${t("sched.registerBtn")}
                    </button>
                </div>

            </section>
        `;
    }

    return `
        <section class="card">

            <h2>${t("sd.current.title")}</h2>

            <table class="sd-table">

                <thead>
                    <tr>
                        <th>${t("sd.col.code")}</th>
                        <th>${t("sd.col.course")}</th>
                        <th>${t("sd.col.instructor")}</th>
                        <th>${t("sd.col.schedule")}</th>
                        <th>${t("sd.col.credits")}</th>
                        <th>${t("sd.col.status")}</th>
                    </tr>
                </thead>

                <tbody>

                    ${info.current.map(c => `
                        <tr>
                            <td data-label="${t("sd.col.code")}">${esc(c.code)}</td>
                            <td data-label="${t("sd.col.course")}"><strong>${esc(loc(c.name))}</strong></td>
                            <td data-label="${t("sd.col.instructor")}">${esc(c.instructor)}</td>
                            <td data-label="${t("sd.col.schedule")}">
                                ${t("day." + c.day)} ${sdTime(c)}<br>
                                <span class="sd-muted">${sdRoom(c)}</span>
                            </td>
                            <td data-label="${t("sd.col.credits")}">${c.credits}</td>
                            <td data-label="${t("sd.col.status")}">
                                <span class="sd-grade sd-now">${t("sd.inProgress")}</span>
                            </td>
                        </tr>
                    `).join("")}

                </tbody>

            </table>

        </section>
    `;
}

function sdCompletedCourses(info) {

    if (info.semesters.length === 0) {

        return `
            <section class="card">
                <h2>${t("sd.completed.title")}</h2>
                <div class="empty">${t("sd.completed.empty")}</div>
            </section>
        `;
    }

    // newest semester first
    const list = info.semesters.slice().reverse();

    return `
        <section class="card">

            <h2 style="margin-bottom:14px">${t("sd.completed.title")}</h2>

            ${list.map((s, index) => `

                <details class="sd-term" ${index === 0 ? "open" : ""}>

                    <summary>
                        <span>${esc(termLabel(s))}</span>
                        <span class="sd-term-sum">
                            ${t("sd.semesterSummary", {
                                gpa: fmtGpa(s.gpa),
                                credits: s.credits
                            })}
                        </span>
                    </summary>

                    <div class="sd-table-wrap">

                        <table class="sd-table">

                            <thead>
                                <tr>
                                    <th>${t("sd.col.code")}</th>
                                    <th>${t("sd.col.course")}</th>
                                    <th>${t("sd.col.credits")}</th>
                                    <th>${t("sd.col.grade")}</th>
                                    <th>${t("sd.col.points")}</th>
                                </tr>
                            </thead>

                            <tbody>

                                ${s.courses.map(c => `
                                    <tr>
                                        <td data-label="${t("sd.col.code")}">${esc(c.code)}</td>
                                        <td data-label="${t("sd.col.course")}"><strong>${esc(loc(c.name))}</strong></td>
                                        <td data-label="${t("sd.col.credits")}">${c.credits}</td>
                                        <td data-label="${t("sd.col.grade")}"><span class="sd-grade">${esc(c.grade)}</span></td>
                                        <td data-label="${t("sd.col.points")}">${gradePointsOf(c.grade).toFixed(2)}</td>
                                    </tr>
                                `).join("")}

                            </tbody>

                        </table>

                    </div>

                </details>

            `).join("")}

        </section>
    `;
}

// =================================
// THE PAGE
// =================================
function showStudentDashboard() {

    const user = currentUser;
    const isStudent = (user.role || "student") === "student";
    const info = StudentAPI.summary(user);

    app.innerHTML = `
        ${header()}

        <main class="container">

            <h1 class="page-title">${t("sd.title")}</h1>

            <p class="subtitle">${t("sd.subtitle")}</p>

            <p class="sd-note">
                ${isStudent ? t("sd.demoNote") : t("sd.notStudent")}
            </p>

            <div class="sd-top">

                ${sdProfileCard(user, info, isStudent)}

                ${isStudent ? sdStats(info) : ""}

            </div>

            ${isStudent ? `
                ${sdProgress(info)}
                ${sdGpaChart(info)}
                ${sdCurrentCourses(info)}
                ${sdCompletedCourses(info)}
            ` : ""}

        </main>

        <footer class="footer">
            ${t("footer")}
        </footer>
    `;
}
