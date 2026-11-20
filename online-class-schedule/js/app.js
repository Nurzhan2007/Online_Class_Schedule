const app = document.getElementById("app");

// The logged-in user, as returned by the server ({id, name, studentId, email, role}).
let currentUser = null;

// login | register | dashboard | courses | mycourses | schedule | details
let currentView = "login";

let selectedCourseId = null;

const defaultFilters = {
    term: "",
    category: "all",
    day: "all",
    instructor: "all",
    credits: "all",
    onlyAvailable: false,
    sortBy: "code",
    sortDir: "asc"
};

let filters = { ...defaultFilters };

// Last error while loading data from the server (shown with a retry button).
let dataError = null;

// True while a login / registration / enrollment request is running:
// prevents double submissions.
let busy = false;

// True when the catalogue page is drawn with real data (then a background
// refresh only redraws the rows and the search box keeps its focus).
let coursesPageReady = false;

const DATA_VIEWS = ["dashboard", "courses", "mycourses", "schedule", "details"];


function isStudent() {
    return currentUser !== null && (currentUser.role || "student") === "student";
}

function myCourses() {
    return CourseAPI.getMyCourses();
}

function timeRange(c) {
    return esc(c.start) + " - " + esc(c.end);
}

function roomLabel(c) {
    return t("room." + c.room.kind) + " " + esc(c.room.no);
}

function optionList(items, selected) {
    return items.map(item => `
        <option value="${esc(item[0])}"
            ${String(item[0]) === String(selected) ? "selected" : ""}>
            ${esc(item[1])}
        </option>
    `).join("");
}

/* busy state: buttons with data-action are disabled while a request runs;
   data-blocked="true" keeps a button disabled for its own reason
   (already registered, no seats left). */
function setBusy(value) {
    busy = value;

    document.querySelectorAll("button[data-action]").forEach(button => {
        button.disabled = value || button.dataset.blocked === "true";
    });
}

// Errors of user actions. 401 was already handled by onUnauthorized.
function showActionError(error) {
    if (error instanceof ApiError && error.status === 401) {
        return;
    }

    alert(errorMessage(error));
}

/* Loading / error state of the server data */

function dataPlaceholder() {
    if (dataError) {
        return `
            <div class="card empty">
                ${esc(errorMessage(dataError))}<br>
                <button class="btn" onclick="retryLoad()">${t("app.retry")}</button>
            </div>
        `;
    }

    return `<div class="card empty">${t("app.loading")}</div>`;
}

// Data is loaded but the latest refresh failed: show the cached data plus a notice.
function staleDataNotice() {
    return CourseAPI.isLoaded() && dataError ? dataPlaceholder() : "";
}

function retryLoad() {
    dataError = null;
    renderView(currentView);
    refreshData();
}

let refreshing = null;

// Reload catalogue (+ my registrations) from the server, then redraw.
// force: after a change (register/cancel) a load that started earlier may
// carry old data, so wait for it and load once more.
function refreshData(force) {
    if (refreshing) {
        return force ? refreshing.then(() => refreshData(true)) : refreshing;
    }

    refreshing = CourseAPI.load(isStudent())
        .then(() => {
            dataError = null;
        })
        .catch(error => {
            if (!(error instanceof ApiError) || error.status !== 401) {
                dataError = error;
            }
        })
        .finally(() => {
            refreshing = null;

            if (currentUser && DATA_VIEWS.includes(currentView)) {
                redrawWithNewData();
            }
        });

    return refreshing;
}

function redrawWithNewData() {
    if (currentView === "courses" && coursesPageReady && CourseAPI.isLoaded() && !dataError) {
        updateCourseList();
        return;
    }

    renderView(currentView);
}

/* til ayustyrushy */

function langSwitcher(extraClass) {
    return `
        <select
            class="lang-select ${extraClass || ""}"
            aria-label="${t("header.language")}"
            onchange="changeLanguage(this.value)">

            ${Object.keys(LANGS).map(code => `
                <option value="${code}"
                    ${code === currentLang ? "selected" : ""}>
                    ${LANGS[code]}
                </option>
            `).join("")}

        </select>
    `;
}

function changeLanguage(lang) {
    setLanguage(lang);
    render();
}

// Re-draws the page the user is currently on (no new requests)
function render() {

    document.title = t("app.title");

    if (currentView === "register") {
        showRegister();
        return;
    }

    if (!currentUser || currentView === "login") {
        showLogin();
        return;
    }

    renderView(currentView);
}

/* start-up screen while the session is being restored */

function showStartupLoading() {
    app.innerHTML = `
        <div class="login-page">
            <div class="login-form">
                <h2>${t("app.loading")}</h2>
            </div>
        </div>
    `;
}

/* login page */

function showLogin() {

    currentView = "login";

    document.title = t("app.title");

    app.innerHTML = `
        <div class="login-page">

            ${langSwitcher("lang-floating")}

            <form class="login-form" id="loginForm">

                <h2>${t("login.title")}</h2>

                <div class="login-field">
                    <label for="loginEmail">${t("login.email")}</label>

                    <input
                        id="loginEmail"
                        type="email"
                        name="email"
                        required
                    >
                </div>

                <div class="login-field">
                    <label for="loginPassword">${t("login.password")}</label>

                    <input
                        id="loginPassword"
                        type="password"
                        name="password"
                        required
                    >
                </div>

                <button class="login-button" type="submit" data-action="login">
                    ${t("login.button")}
                </button>

                <p class="login-switch">
                    ${t("login.newStudent")}
                    <a onclick="showRegister()">${t("login.register")}</a>
                </p>

            </form>

        </div>
    `;

    document.getElementById("loginForm").onsubmit = async function(e) {

        e.preventDefault();

        if (busy) return;

        const formData = new FormData(this);

        const email = formData.get("email").trim();
        const password = formData.get("password");

        setBusy(true);

        try {
            currentUser = await Auth.login(email, password);
        } catch (error) {
            // auth.invalid {n attempts left} / auth.locked {time} - exactly what the server says
            alert(errorMessage(error));
            return;
        } finally {
            setBusy(false);
        }

        CourseAPI.clear();
        dataError = null;
        filters = { ...defaultFilters };

        navigate("dashboard");
    };
}

/* registration pagee */

function showRegister() {

    currentView = "register";

    document.title = t("app.title");

    app.innerHTML = `
        <div class="register-page">

            ${langSwitcher("lang-floating")}

            <div class="register-box">

                <h2>${t("reg.title")}</h2>

                <form id="registerForm">

                    <label>${t("reg.fullName")}</label>
                    <input
                        name="name"
                        type="text"
                        placeholder="${t("reg.namePh")}"
                        required
                    >

                    <label>${t("reg.studentId")}</label>
                    <input
                        name="studentId"
                        type="text"
                        placeholder="24B031234"
                        required
                    >

                    <label>${t("login.email")}</label>
                    <input
                        name="email"
                        type="email"
                        placeholder="student@kbtu.kz"
                        required
                    >

                    <label>${t("login.password")}</label>
                    <input
                        name="password"
                        type="password"
                        minlength="6"
                        placeholder="${t("reg.passwordPh")}"
                        required
                    >

                    <button class="btn" type="submit" data-action="signup">
                        ${t("reg.create")}
                    </button>

                </form>

                <p class="form-switch">
                    ${t("reg.already")}
                    <a onclick="showLogin()">${t("login.button")}</a>
                </p>

            </div>

        </div>
    `;

    document.getElementById("registerForm").onsubmit = async function(e) {

        e.preventDefault();

        if (busy) return;

        const formData = new FormData(this);

        setBusy(true);

        try {
            // Creates a real student account in the database.
            await Auth.register({
                name: formData.get("name"),
                studentId: formData.get("studentId"),
                email: formData.get("email"),
                password: formData.get("password")
            });
        } catch (error) {
            alert(errorMessage(error));
            return;
        } finally {
            setBusy(false);
        }

        alert(t("reg.success"));

        showLogin();
    };
}

/* header */

function header() {

    const role = currentUser.role || "student";

    return `
        <header class="header">

            <div class="header-logo">
                <img
                    src="assets/kbtu-logo.png"
                    alt="KBTU Logo"
                >
            </div>

            <div class="header-right">

                <div class="user-info">
                    ${t("header.loggedInAs")} ${esc(currentUser.name)}
                    <span class="role-label">
                        ${esc(t("role." + role).toUpperCase())}
                    </span>
                </div>

                ${langSwitcher()}

                <button class="header-logout" onclick="logout()">
                    ${t("nav.logout")}
                </button>

            </div>

        </header>

        <nav class="nav">

            <button onclick="navigate('dashboard')">
                ${t("nav.home")}
            </button>

            <button onclick="navigate('courses')">
                ${t("nav.courses")}
            </button>

            <button onclick="navigate('mycourses')">
                ${t("nav.myCourses")}
            </button>

            <button onclick="navigate('schedule')">
                ${t("nav.schedule")}
            </button>


        </nav>
    `;
}

/* navigation */

function renderView(page) {

    document.title = t("app.title");

    if (page === "dashboard") showDashboard();

    if (page === "courses") showCourses();

    if (page === "mycourses") showMyCourses();

    if (page === "schedule") showUniversitySchedule();

    if (page === "details") showCourseDetails();
}

// Show a page from the cache at once, then refresh its data from the server.
function navigate(page) {

    if (!currentUser || !validateAccessToken()) {
        endSession();
        return;
    }

    currentView = page;

    renderView(page);

    if (page === "details") {
        refreshSelectedCourse();
    } else {
        refreshData();
    }
}

/* dashboard */

function showDashboard() {

    const registered = myCourses();

    const studentId = currentUser.studentId
        ? " · " + esc(t("dash.studentId", { id: currentUser.studentId }))
        : "";

    app.innerHTML = `
        ${header()}

        <main class="container">

            <h1 class="page-title">
                ${t("dash.welcome", { name: esc(currentUser.name) })}
            </h1>

            <p class="subtitle">
                ${t("dash.subtitle")}${studentId}
            </p>

            ${!CourseAPI.isLoaded() ? dataPlaceholder() : `

            ${staleDataNotice()}

            <div class="grid">

                <div class="card">
                    <p>${t("dash.available")}</p>

                    <div class="stat-number">
                        ${CourseAPI.getAll().length}
                    </div>

                    <button class="btn"
                        onclick="navigate('courses')">
                        ${t("dash.browse")}
                    </button>
                </div>

                <div class="card">
                    <p>${t("dash.registered")}</p>

                    <div class="stat-number">
                        ${registered.length}
                    </div>

                    <button class="btn"
                        onclick="navigate('mycourses')">
                        ${t("dash.viewMy")}
                    </button>
                </div>

                <div class="card">
                    <p>${t("dash.credits")}</p>

                    <div class="stat-number">
                        ${CourseAPI.getTotalCredits()}
                    </div>

                    <span class="badge">
                        ${t("dash.semester")}
                    </span>
                </div>

            </div>

            <div class="card">

                <h2>${t("dash.weekly")}</h2>

                <br>

                ${scheduleTable(registered)}

            </div>
            `}

        </main>

        <footer class="footer">
            ${t("footer")}
        </footer>
    `;
}

/* Weekly schedule table */

function scheduleTable(registered, showAll = false) {
    if (registered.length === 0 && !showAll) {
        return `
            <div class="empty">
                ${t("sched.empty")}<br>
                <button class="btn" onclick="navigate('courses')">
                    ${t("sched.registerBtn")}
                </button>
            </div>
        `;
    }

    const times = [...new Set(registered.map(c => c.start))].sort();

    return `
        <div class="schedule-wrapper">
            <table class="weekly-table">
                <thead>
                    <tr>
                        <th>${t("sched.time")}</th>
                        ${DAY_ORDER.map(day => `<th>${t("day." + day)}</th>`).join("")}
                    </tr>
                </thead>
                <tbody>
                    ${times.map(time => `
                        <tr>
                            <td class="time-cell">${esc(time)}</td>
                            ${DAY_ORDER.map(day => {
                                const courses = registered.filter(c =>
                                    c.day === day && c.start === time
                                );

                                return `
                                    <td>
                                        ${courses.length
                                            ? courses.map(course => `
                                                <div class="schedule-course">
                                                    <strong>${esc(loc(course.name))}</strong>
                                                    <span>${esc(course.code)}</span>
                                                    <span>${timeRange(course)}</span>
                                                    <span>${esc(course.instructor)}</span>
                                                    <span>${roomLabel(course)}</span>
                                                </div>
                                            `).join("")
                                            : `<span class="free-time"> </span>`
                                        }
                                    </td>
                                `;
                            }).join("")}
                        </tr>
                    `).join("")}
                </tbody>
            </table>

            <div class="schedule-mobile">
                ${DAY_ORDER.map(day => {
                    const courses = registered
                        .filter(course => course.day === day)
                        .sort((a, b) => a.start.localeCompare(b.start));

                    if (!courses.length) return "";

                    return `
                        <section class="mobile-day">
                            <h3>${t("day." + day)}</h3>
                            ${courses.map(course => `
                                <article class="schedule-course mobile-course">
                                    <strong>${esc(loc(course.name))}</strong>
                                    <span>${esc(course.code)}</span>
                                    <span>${timeRange(course)}</span>
                                    <span>${esc(course.instructor)}</span>
                                    <span>${roomLabel(course)}</span>
                                </article>
                            `).join("")}
                        </section>
                    `;
                }).join("")}
            </div>
        </div>
    `;
}

function showUniversitySchedule() {
    const courses = CourseAPI.getAll();
    app.innerHTML = `
        ${header()}
        <main class="container">
            <h1 class="page-title">${t("schedule.title")}</h1>
            <p class="subtitle">${t("schedule.subtitle")}</p>
            ${!CourseAPI.isLoaded() ? dataPlaceholder() : `
            ${staleDataNotice()}
            <div class="card schedule-legend"><span class="schedule-dot"></span>${t("schedule.legend")}</div>
            <div class="card">${scheduleTable(courses, true)}</div>
            `}
        </main>
        <footer class="footer">${t("footer")}</footer>`;
}

/* course catalog */
const SORT_COLUMNS = [
    ["code", "col.code"],
    ["name", "col.course"],
    ["instructor", "course.instructor"],
    ["credits", "course.credits"],
    ["day", "col.schedule"],
    ["seats", "course.seats"]
];

function sortArrow(key) {

    if (filters.sortBy !== key) return "";

    return filters.sortDir === "desc" ? " ▼" : " ▲";
}

function setSort(key) {

    if (filters.sortBy === key) {

        filters.sortDir = filters.sortDir === "asc" ? "desc" : "asc";

    } else {

        filters.sortBy = key;
        filters.sortDir =
            (key === "credits" || key === "seats") ? "desc" : "asc";
    }

    showCourses();
}

function courseRow(c) {

    const seats = CourseAPI.getSeatsLeft(c.id);

    return `
        <div class="course-row">

            <div class="cell cell-code" data-label="${t("col.code")}">
                ${esc(c.code)}
            </div>

            <div class="cell cell-name">
                <strong>${esc(loc(c.name))}</strong>
                <span class="badge">${t("cat." + c.category)}</span>
            </div>

            <div class="cell" data-label="${t("course.instructor")}">
                ${esc(c.instructor)}
            </div>

            <div class="cell" data-label="${t("course.credits")}">
                ${c.credits}
            </div>

            <div class="cell" data-label="${t("col.schedule")}">
                ${t("day." + c.day)}<br>
                <span class="muted">
                    ${timeRange(c)} · ${roomLabel(c)}
                </span>
            </div>

            <div class="cell" data-label="${t("course.seats")}">
                <span class="${seats === 0 ? "seats-full" : ""}">
                    ${seats}
                </span>
            </div>

            <div class="cell cell-action">
                <button class="btn btn-small"
                    onclick="openCourse(${c.id})">
                    ${t("course.viewDetails")}
                </button>
            </div>

        </div>
    `;
}

// Updates only the course rows
function updateCourseList() {

    const list = CourseAPI.search(filters);

    document.getElementById("resultCount").textContent =
        t("filter.results", { count: list.length });

    document.getElementById("courseRows").innerHTML = list.length
        ? list.map(courseRow).join("")
        : `<div class="card empty">${t("course.noResults")}</div>`;
}

function showCourses() {

    if (!CourseAPI.isLoaded()) {

        coursesPageReady = false;

        app.innerHTML = `
            ${header()}
            <main class="container">
                <h1 class="page-title">${t("catalog.title")}</h1>
                <p class="subtitle">${t("catalog.subtitle")}</p>
                ${dataPlaceholder()}
            </main>
            <footer class="footer">${t("footer")}</footer>
        `;
        return;
    }

    const categoryItems = [["all", t("cat.all")]].concat(
        CourseAPI.getCategories().map(cat => [cat, t("cat." + cat)])
    );

    const dayItems = [["all", t("filter.any")]].concat(
        DAY_ORDER.map(day => [day, t("day." + day)])
    );

    const instructorItems = [["all", t("filter.any")]].concat(
        CourseAPI.getInstructors().map(name => [name, name])
    );

    const creditItems = [["all", t("filter.any")]].concat(
        CourseAPI.getCreditOptions().map(n => [n, String(n)])
    );

    const sortItems = SORT_COLUMNS.map(col => [
        col[0],
        t("sort." + col[0])
    ]);

    const directionLabel = filters.sortDir === "desc"
        ? "▼ " + t("sort.desc")
        : "▲ " + t("sort.asc");

    app.innerHTML = `
        ${header()}

        <main class="container">

            <h1 class="page-title">
                ${t("catalog.title")}
            </h1>

            <p class="subtitle">
                ${t("catalog.subtitle")}
            </p>

            ${staleDataNotice()}

            <div class="card">

                <div class="filters-grid">

                    <div class="filter-wide">
                        <label for="courseSearch">${t("filter.search")}</label>

                        <input
                            id="courseSearch"
                            placeholder="${t("filter.searchPh")}"
                            value="${esc(filters.term)}"
                        >
                    </div>

                    <div>
                        <label for="categoryFilter">${t("filter.category")}</label>

                        <select id="categoryFilter">
                            ${optionList(categoryItems, filters.category)}
                        </select>
                    </div>

                    <div>
                        <label for="dayFilter">${t("filter.day")}</label>

                        <select id="dayFilter">
                            ${optionList(dayItems, filters.day)}
                        </select>
                    </div>

                    <div>
                        <label for="instructorFilter">${t("filter.instructor")}</label>

                        <select id="instructorFilter">
                            ${optionList(instructorItems, filters.instructor)}
                        </select>
                    </div>

                    <div>
                        <label for="creditsFilter">${t("filter.credits")}</label>

                        <select id="creditsFilter">
                            ${optionList(creditItems, filters.credits)}
                        </select>
                    </div>

                    <div>
                        <label for="sortFilter">${t("filter.sort")}</label>

                        <div class="sort-controls">

                            <select id="sortFilter">
                                ${optionList(sortItems, filters.sortBy)}
                            </select>

                            <button id="sortDirection"
                                class="btn btn-light"
                                type="button">
                                ${directionLabel}
                            </button>

                        </div>
                    </div>

                </div>

                <div class="filter-actions">

                    <label class="checkbox-row">
                        <input
                            id="availableFilter"
                            type="checkbox"
                            ${filters.onlyAvailable ? "checked" : ""}
                        >
                        ${t("filter.onlyAvailable")}
                    </label>

                    <button id="resetFilters" class="btn btn-light">
                        ${t("filter.reset")}
                    </button>

                </div>

            </div>

            <p class="result-count" id="resultCount"></p>

            <div class="course-list-head">

                ${SORT_COLUMNS.map(col => `
                    <button
                        class="sort-btn ${filters.sortBy === col[0] ? "active" : ""}"
                        onclick="setSort('${col[0]}')">
                        ${t(col[1])}${sortArrow(col[0])}
                    </button>
                `).join("")}

                <span></span>

            </div>

            <div class="course-list" id="courseRows"></div>

        </main>

        <footer class="footer">
            ${t("footer")}
        </footer>
    `;

    coursesPageReady = !dataError;

    document.getElementById("courseSearch").oninput = function() {
        filters.term = this.value;
        updateCourseList();
    };

    [
        ["categoryFilter", "category"],
        ["dayFilter", "day"],
        ["instructorFilter", "instructor"],
        ["creditsFilter", "credits"]
    ].forEach(pair => {

        document.getElementById(pair[0]).onchange = function() {
            filters[pair[1]] = this.value;
            updateCourseList();
        };
    });

    // Sort field changed from the dropdown: same direction defaults as headers
    document.getElementById("sortFilter").onchange = function() {

        filters.sortBy = this.value;

        filters.sortDir =
            (this.value === "credits" || this.value === "seats")
                ? "desc"
                : "asc";

        showCourses();
    };

    document.getElementById("sortDirection").onclick = function() {

        filters.sortDir = filters.sortDir === "asc" ? "desc" : "asc";

        showCourses();
    };

    document.getElementById("availableFilter").onchange = function() {
        filters.onlyAvailable = this.checked;
        updateCourseList();
    };

    document.getElementById("resetFilters").onclick = function() {
        filters = { ...defaultFilters };
        showCourses();
    };

    updateCourseList();
}

/* courstar turali */

function openCourse(id) {

    selectedCourseId = id;

    navigate("details");
}

// Fresh seat count for the open course (GET /api/courses/{id}).
function refreshSelectedCourse() {
    const id = selectedCourseId;

    CourseAPI.refreshCourse(id)
        .then(() => {
            if (currentUser && currentView === "details" && selectedCourseId === id && !busy) {
                showCourseDetails();
            }
        })
        .catch(error => {
            if (error instanceof ApiError && error.status === 401) return;

            if (error instanceof ApiError && error.status === 404) {
                navigate("courses");   // the course no longer exists
                return;
            }

            dataError = error;

            if (currentView === "details") showCourseDetails();
        });
}

function showCourseDetails() {

    const c = CourseAPI.getById(selectedCourseId);

    if (!c) {

        if (CourseAPI.isLoaded()) {
            navigate("courses");
            return;
        }

        app.innerHTML = `
            ${header()}
            <main class="container">${dataPlaceholder()}</main>
        `;
        return;
    }

    const isRegistered = CourseAPI.isRegistered(c.id);

    const seats = CourseAPI.getSeatsLeft(c.id);

    const blocked = isRegistered || seats <= 0;

    let buttonLabel = t("course.register");

    if (isRegistered) {
        buttonLabel = t("course.already");
    } else if (seats <= 0) {
        buttonLabel = t("course.full");
    }

    app.innerHTML = `
        ${header()}

        <main class="container">

            <button class="btn btn-light"
                onclick="navigate('courses')">
                ${t("course.back")}
            </button>

            <div class="card" style="margin-top:25px">

                <p class="course-code">
                    ${esc(c.code)}
                </p>

                <h1 class="page-title">
                    ${esc(loc(c.name))}
                </h1>

                <p class="subtitle">
                    ${t("cat." + c.category)}
                </p>

                <h3>${t("course.description")}</h3>

                <p style="margin:15px 0;line-height:1.7">
                    ${esc(loc(c.description))}
                </p>

                <div class="course-instructor">

                    <img
                        class="instructor-photo"
                         src="${c.id === 21
                        ? 'assets/17515516682151.png'
                        : 'assets/137420f5b9c39bc911e472f5d20f053e.jpg'}"
                        alt="${esc(c.instructor)}"
                    >
                    <div>
                        <span class="instructor-label">${t("course.instructor")}</span>
                        <strong>${esc(c.instructor)}</strong>
                    </div>
                </div>

                <hr>

                <br>

                <p class="course-meta">

                    <strong>${t("course.credits")}:</strong> ${c.credits}<br>

                    <strong>${t("course.day")}:</strong> ${t("day." + c.day)}<br>

                    <strong>${t("course.time")}:</strong> ${timeRange(c)}<br>

                    <strong>${t("course.location")}:</strong> ${roomLabel(c)}

                </p>

                <div class="section-picker">
                    <h3>${t("section.title")}</h3>
                    <p class="muted">${t("section.help")}</p>
                    <div class="registration-seats">
                        <span>${t("course.seats")}</span>
                        <strong>${seats}</strong>
                    </div>
                </div>

                <button class="btn"
                    id="registerButton"
                    data-action="register"
                    data-blocked="${blocked}"
                    onclick="registerCourse(${c.id})"
                    ${blocked || busy ? "disabled" : ""}>

                    ${buttonLabel}

                </button>

            </div>

        </main>
    `;
}

/* register */

async function registerCourse(id) {

    if (busy) return;   // a request is already running

    if (!requireRole("student")) return;

    const course = CourseAPI.getById(id);

    if (!course) return;

    setBusy(true);

    let registered = false;

    try {
        // Same checks as the real registration, nothing is saved yet.
        await CourseAPI.checkRegistration(id);

        if (!confirm(t("confirm.register", { name: loc(course.name) }))) {
            return;
        }

        // Only the course id is sent; the server re-checks everything.
        await CourseAPI.register(id);
        registered = true;

        alert(t("msg.registered", { name: loc(course.name) }));

    } catch (error) {
        showActionError(error);   // err.alreadyRegistered / err.noSeats / err.conflict ...
    } finally {
        setBusy(false);
    }

    if (!currentUser) return;

    if (registered) {
        currentView = "mycourses";
    }

    // Seats and registrations from the server (also after an error:
    // the last seat may have been taken by someone else).
    await refreshData(true);
}

/* my courses osy jerde tur*/

function showMyCourses() {

    const registered = myCourses();

    app.innerHTML = `
        ${header()}

        <main class="container">

            <h1 class="page-title">
                ${t("mycourses.title")}
            </h1>

            <p class="subtitle">
                ${t("mycourses.subtitle")}
            </p>

            ${!CourseAPI.isLoaded() ? dataPlaceholder() : staleDataNotice() + (registered.length ? `

                <div class="grid">

                    ${registered.map(c => `

                        <div class="card">

                            <p class="course-code">
                                ${esc(c.code)}
                            </p>

                            <h3>${esc(loc(c.name))}</h3>

                            <p class="course-meta">

                                ${esc(c.instructor)}<br>

                                ${t("day." + c.day)} | ${timeRange(c)}<br>

                                ${t("course.credits")}: ${c.credits}

                            </p>

                            <span class="badge">
                                ${t("course.registeredBadge")}
                            </span>

                            <br>

                            <button class="btn btn-light"
                                data-action="unregister"
                                onclick="unregisterCourse(${c.id})"
                                ${busy ? "disabled" : ""}>
                                ${t("course.unregister")}
                            </button>

                        </div>

                    `).join("")}

                </div>

            ` : `

                <div class="card empty">

                    ${t("mycourses.none")}

                    <br>

                    <button class="btn"
                        onclick="navigate('courses')">
                        ${t("dash.browse")}
                    </button>

                </div>

            `)}

        </main>

        <footer class="footer">
            ${t("footer")}
        </footer>
    `;
}

/* registerdi kaitaru*/

async function unregisterCourse(id) {

    if (busy) return;

    if (!requireRole("student")) return;

    if (!confirm(t("confirm.unregister"))) {
        return;
    }

    setBusy(true);

    try {
        await CourseAPI.unregister(id);
    } catch (error) {
        showActionError(error);
    } finally {
        setBusy(false);
    }

    if (currentUser) {
        await refreshData(true);   // my courses + seats from the server
    }
}

/* logout */

async function logout() {

    if (busy) return;

    setBusy(true);

    await Auth.logout();   // revokes the token on the server

    setBusy(false);

    endSession();
}

// Forget everything about the session and show the login page.
function endSession() {
    currentUser = null;
    Auth.clearSession();
    CourseAPI.clear();
    dataError = null;
    filters = { ...defaultFilters };
    showLogin();
}

// A protected request answered 401: token expired, revoked or missing.
ApiClient.onUnauthorized = function(error) {

    if (!currentUser) return;   // already handled (parallel requests)

    currentUser = null;

    alert(t(error.code === "auth.sessionExpired" ? "auth.sessionExpired" : "auth.loginFirst"));

    endSession();
};

/* start-up: restore the session after a page refresh */

async function boot() {

    document.title = t("app.title");

    if (TokenStore.status() !== "valid") {
        TokenStore.clear();
        showLogin();
        return;
    }

    showStartupLoading();

    try {
        currentUser = await Auth.restore();   // GET /api/auth/me
    } catch (error) {
        Auth.clearSession();
        showLogin();

        // 401: the token was revoked or has expired - just log in again.
        if (!(error instanceof ApiError) || error.status !== 401) {
            alert(errorMessage(error));
        }
        return;
    }

    if (!currentUser) {
        showLogin();
        return;
    }

    navigate("dashboard");
}

boot();
