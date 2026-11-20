/* =========================================================
   CourseAPI - course catalogue and the student's registrations,
   loaded from the backend:
     GET  /api/courses, /api/courses/meta, /api/courses/{id}
     GET  /api/me/registrations
     POST /api/me/registrations/check, POST /api/me/registrations
     DELETE /api/me/registrations/{course_id}

   The screens are drawn synchronously, so the data is kept in an
   in-memory cache that is filled asynchronously (load/refresh).
   isLoaded() is false until the first load has really finished.
   The server is the authority for seats, enrollment and the
   timetable; nothing about them is stored in the browser.
   ========================================================= */

const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri"];

const EMPTY_REGISTRATIONS = { courses: [], count: 0, totalCredits: 0 };

function timeToMinutes(value) {
    const parts = value.split(":");

    return Number(parts[0]) * 60 + Number(parts[1]);
}

const CourseAPI = {

    _courses: [],
    _byId: new Map(),
    _meta: null,
    _mine: EMPTY_REGISTRATIONS,
    _loaded: false,

    isLoaded() {
        return this._loaded;
    },

    // Catalogue + filter options (+ the student's registrations).
    // Teachers and admins have no registrations (the API answers 403).
    async load(includeRegistrations) {
        const [courses, meta, mine] = await Promise.all([
            ApiClient.get("/courses"),
            ApiClient.get("/courses/meta"),
            includeRegistrations ? ApiClient.get("/me/registrations") : Promise.resolve(EMPTY_REGISTRATIONS)
        ]);

        this._setCourses(courses);
        this._meta = meta;
        this._mine = mine;
        this._loaded = true;
    },

    // Fresh copy of one course (seat count), used by the details page.
    async refreshCourse(id) {
        const course = await ApiClient.get("/courses/" + id);
        const index = this._courses.findIndex(c => c.id === course.id);

        if (index >= 0) {
            this._courses[index] = course;
        } else {
            this._courses.push(course);
        }

        this._byId.set(course.id, course);

        return course;
    },

    clear() {
        this._setCourses([]);
        this._meta = null;
        this._mine = EMPTY_REGISTRATIONS;
        this._loaded = false;
    },

    _setCourses(courses) {
        this._courses = courses;
        this._byId = new Map(courses.map(course => [course.id, course]));
    },

    /* ------------------------------ catalogue (from cache) */

    getAll() {
        return this._courses;
    },

    getById(id) {
        return this._byId.get(id) || null;
    },

    getCategories() {
        return this._meta ? this._meta.categories : [];
    },

    getInstructors() {
        return this._meta ? this._meta.instructors : [];
    },

    getCreditOptions() {
        return this._meta ? this._meta.credits : [];
    },

    getSeatsLeft(id) {
        const course = this.getById(id);

        return course ? course.seatsLeft : 0;
    },

    /* ------------------------------ my registrations (from cache) */

    // Registered courses with their official schedule, catalogue order.
    getMyCourses() {
        return this._mine.courses;
    },

    getRegisteredIds() {
        return this._mine.courses.map(course => course.id);
    },

    isRegistered(id) {
        return this.getRegisteredIds().includes(id);
    },

    getTotalCredits() {
        return this._mine.totalCredits;
    },

    /* ------------------------------ search, filters, sorting */

    // filters: { term, category, day, instructor, credits, onlyAvailable, sortBy, sortDir }
    // Runs on the loaded catalogue, exactly as before, so typing in the
    // search box stays instant and the sort uses the selected language.
    search(filters) {
        const f = filters || {};
        const term = (f.term || "").trim().toLowerCase();

        const list = this._courses.filter(course => {

            if (term) {
                const haystack = [
                    course.code,
                    course.instructor,
                    course.name.en,
                    course.name.ru,
                    course.name.kk
                ].join(" ").toLowerCase();

                if (!haystack.includes(term)) return false;
            }

            if (f.category && f.category !== "all" &&
                course.category !== f.category) return false;

            if (f.day && f.day !== "all" &&
                course.day !== f.day) return false;

            if (f.instructor && f.instructor !== "all" &&
                course.instructor !== f.instructor) return false;

            if (f.credits && f.credits !== "all" &&
                course.credits !== Number(f.credits)) return false;

            if (f.onlyAvailable &&
                this.getSeatsLeft(course.id) <= 0) return false;

            return true;
        });

        const sortBy = f.sortBy || "code";
        const direction = f.sortDir === "desc" ? -1 : 1;

        const byCode = (a, b) =>
            a.code.localeCompare(b.code, "en", { numeric: true });

        const comparators = {
            code: byCode,

            name: (a, b) =>
                loc(a.name).localeCompare(loc(b.name), currentLang),

            instructor: (a, b) =>
                a.instructor.localeCompare(b.instructor, "en"),

            credits: (a, b) => a.credits - b.credits,

            seats: (a, b) =>
                this.getSeatsLeft(a.id) - this.getSeatsLeft(b.id),

            // day of week first, then start time
            day: (a, b) =>
                DAY_ORDER.indexOf(a.day) - DAY_ORDER.indexOf(b.day) ||
                timeToMinutes(a.start) - timeToMinutes(b.start)
        };

        const compare = comparators[sortBy] || byCode;

        return list.slice().sort((a, b) => direction * compare(a, b) || byCode(a, b));
    },

    /* ------------------------------ registration (server decides) */

    // Dry run: resolves {ok, seatsLeft} or rejects with the same ApiError
    // as a real registration (err.alreadyRegistered / err.noSeats / err.conflict ...).
    checkRegistration(id) {
        return ApiClient.post("/me/registrations/check", { courseId: id });
    },

    // Only the course id is sent: the student comes from the token and
    // the schedule is the course's fixed university schedule.
    register(id) {
        return ApiClient.post("/me/registrations", { courseId: id });
    },

    unregister(id) {
        return ApiClient.delete("/me/registrations/" + id);
    }
};
