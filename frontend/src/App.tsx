
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import "./App.css";
import { useAuth } from "./auth/auth-context";
import AuthScreen from "./auth/AuthScreen";

// Backend health response
interface HealthResponse {
  status: string;
  application: string;
}

// Project data structure
interface Project {
  id: number;
  name: string;
  hackathon_name: string;
  problem_statement: string;
  description: string;
  tech_stack: string;
  development_stage: string;
  created_at: string;
}

function Dashboard() {
  const { user, signOut, error: authError } = useAuth();

  // Application state
  const [backend, setBackend] = useState<HealthResponse | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);

  // Projects state
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  // Create project modal state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Selected project state
  const [selectedProject, setSelectedProject] =
    useState<Project | null>(null);

  const userEmail = user?.email?.trim();
  const displayEmail = userEmail || "Signed-in user";
  const avatarInitial = userEmail?.charAt(0).toUpperCase() || "U";
  const signOutErrorMessage =
    signOutError ??
    (authError ? "Unable to sign out. Please try again." : null);

  // Create a new project
  const handleCreateProject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormSubmitting(true);
    setFormError(null);

    const formData = new FormData(event.currentTarget);

    const projectData = {
      name: formData.get("name") as string,
      hackathon_name: formData.get("hackathon_name") as string,
      problem_statement: formData.get("problem_statement") as string,
      description: formData.get("description") as string,
      tech_stack: formData.get("tech_stack") as string,
      development_stage: formData.get("development_stage") as string,
    };

    try {
      const response = await fetch("http://127.0.0.1:8000/api/projects", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(projectData),
      });

      if (!response.ok) {
        throw new Error("Failed to create project");
      }

      const newProject: Project = await response.json();

      setProjects((currentProjects) => [
        newProject,
        ...currentProjects,
      ]);

      setShowCreateForm(false);
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Something went wrong"
      );
    } finally {
      setFormSubmitting(false);
    }
  };

  // Return to dashboard
  const handleBackToDashboard = () => {
    setSelectedProject(null);
  };

  const handleSignOut = async () => {
    setSignOutError(null);
    setSigningOut(true);

    try {
      await signOut();
    } catch {
      setSignOutError("Unable to sign out. Please try again.");
    } finally {
      setSigningOut(false);
    }
  };

  // Check backend connection
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Backend unavailable");
        }

        return response.json();
      })
      .then((data: HealthResponse) => setBackend(data))
      .catch(() => setBackend(null));
  }, []);

  // Fetch all projects
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/projects")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to fetch projects");
        }

        return response.json();
      })
      .then((data: Project[]) => {
        setProjects(data);
        setProjectsError(null);
      })
      .catch((error: Error) => {
        setProjectsError(error.message);
      })
      .finally(() => {
        setProjectsLoading(false);
      });
  }, []);

  return (
    <div className={`app ${darkMode ? "dark" : "light"}`}>
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">H</div>

          <div>
            <h2>HACKPRENEUR</h2>
            <span>Project Continuity Platform</span>
          </div>
        </div>

        <div className="nav-section">
          <p className="nav-label">WORKSPACE</p>

          <button className="nav-item active">Overview</button>
          <button className="nav-item">My Projects</button>
          <button className="nav-item">Roadmaps</button>

          <p className="nav-label">GROWTH</p>

          <button className="nav-item">Mentor Matching</button>
          <button className="nav-item">Feedback</button>
          <button className="nav-item">Progress</button>
        </div>

        <div className="sidebar-bottom">
          <div className="user-profile">
            <div className="avatar">{avatarInitial}</div>

            <div style={{ minWidth: 0 }}>
              <strong
                title={displayEmail}
                style={{
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {displayEmail}
              </strong>
              <span>Workspace</span>
            </div>
          </div>

          <button
            type="button"
            className="secondary-button"
            onClick={handleSignOut}
            disabled={signingOut}
            style={{ width: "100%", marginTop: 8 }}
          >
            {signingOut ? "Signing out..." : "Sign out"}
          </button>

          {signOutErrorMessage && (
            <p
              className="form-error"
              role="alert"
              style={{ marginTop: 8, marginBottom: 0 }}
            >
              {signOutErrorMessage}
            </p>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {selectedProject ? (
          /* PROJECT DETAILS VIEW */
          <section className="project-details-view">
            <header className="topbar">
              <div>
                <span className="breadcrumb">
                  Workspace / My Projects / Details
                </span>

                <h1>Project Details</h1>
              </div>

              <div className="topbar-actions">
                <button
                  className="theme-toggle"
                  onClick={() => setDarkMode(!darkMode)}
                >
                  {darkMode ? "Light mode" : "Dark mode"}
                </button>

                <button
                  className="secondary-button"
                  onClick={handleBackToDashboard}
                >
                  ← Back to Dashboard
                </button>
              </div>
            </header>

            <div className="details-panel">
              <div className="details-heading">
                <div>
                  <span className="details-label">
                    PROJECT OVERVIEW
                  </span>

                  <h2>{selectedProject.name}</h2>
                  <p>{selectedProject.hackathon_name}</p>
                </div>

                <span className="details-stage">
                  {selectedProject.development_stage}
                </span>
              </div>

              <div className="details-section">
                <h3>Problem Statement</h3>
                <p>{selectedProject.problem_statement}</p>
              </div>

              <div className="details-section">
                <h3>Project Description</h3>
                <p>{selectedProject.description}</p>
              </div>

              <div className="details-section">
                <h3>Technology Stack</h3>
                <p>{selectedProject.tech_stack}</p>
              </div>

              <div className="analysis-entry">
                <div>
                  <h3>Project Intelligence</h3>

                  <p>
                    Understand your project's strengths, gaps and
                    opportunities for further development.
                  </p>
                </div>

                <button className="primary-button" disabled>
                  AI Analysis — Coming Soon
                </button>
              </div>
            </div>
          </section>
        ) : (
          /* DASHBOARD VIEW */
          <>
            <header className="topbar">
              <div>
                <span className="breadcrumb">
                  Workspace / Overview
                </span>

                <h1>Overview</h1>
              </div>

              <button
                className="theme-toggle"
                onClick={() => setDarkMode(!darkMode)}
              >
                {darkMode ? "Light mode" : "Dark mode"}
              </button>
            </header>

            {/* Welcome Section */}
            <section className="welcome-section">
              <div>
                <h2>Your next chapter starts here.</h2>

                <p>
                  Turn your hackathon prototype into a project with a
                  clear path forward.
                </p>
              </div>

              <button
                className="primary-button"
                onClick={() => {
                  setFormError(null);
                  setShowCreateForm(true);
                }}
              >
                + Create project
              </button>
            </section>

            {/* Statistics */}
            <section className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Total Projects</span>
                <h2>{projectsLoading ? "..." : projects.length}</h2>
                <p>Your registered projects</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Active Milestones</span>
                <h2>0</h2>
                <p>Tasks in progress</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Feedback Received</span>
                <h2>0</h2>
                <p>Insights from reviewers</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Project Readiness</span>
                <h2>—</h2>
                <p>Awaiting first analysis</p>
              </div>
            </section>

            {/* Dashboard Content */}
            <section className="content-grid">
              {/* Projects Panel */}
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h3>My Projects</h3>
                    <p>Your hackathon projects in one place.</p>
                  </div>

                  <span className="muted-label">
                    {projects.length}{" "}
                    {projects.length === 1 ? "project" : "projects"}
                  </span>
                </div>

                {projectsLoading ? (
                  <div className="empty-state">
                    <h3>Loading projects...</h3>
                    <p>Fetching your projects from the database.</p>
                  </div>
                ) : projectsError ? (
                  <div className="empty-state">
                    <h3>Unable to load projects</h3>
                    <p>{projectsError}</p>
                  </div>
                ) : projects.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">+</div>

                    <h3>No projects yet</h3>

                    <p>
                      Add your first hackathon project to start building
                      its continuation roadmap.
                    </p>

                    <button
                      className="secondary-button"
                      onClick={() => {
                        setFormError(null);
                        setShowCreateForm(true);
                      }}
                    >
                      Create your first project
                    </button>
                  </div>
                ) : (
                  <div className="project-list">
                    {projects.map((project) => (
                      <div
                        className="project-card"
                        key={project.id}
                        onClick={() => setSelectedProject(project)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" ||
                            event.key === " "
                          ) {
                            event.preventDefault();
                            setSelectedProject(project);
                          }
                        }}
                      >
                        <h3>{project.name}</h3>
                        <p>{project.hackathon_name}</p>
                        <p>{project.description}</p>
                        <span>{project.development_stage}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Backend Status Panel */}
              <div className="panel backend-panel">
                <h3>System Status</h3>
                <p>Application connectivity</p>

                <div className="status-row">
                  <span>Frontend</span>
                  <span className="status online">Online</span>
                </div>

                <div className="status-row">
                  <span>Backend API</span>

                  <span
                    className={`status ${
                      backend ? "online" : "offline"
                    }`}
                  >
                    {backend ? "Connected" : "Disconnected"}
                  </span>
                </div>

                <div className="status-row">
                  <span>Application</span>
                  <span>HACKPRENEUR</span>
                </div>
              </div>
            </section>
          </>
        )}
      </main>

      {/* CREATE PROJECT MODAL */}
      {showCreateForm && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <div>
                <h2>Create a project</h2>
                <p>Add your hackathon project details.</p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() => setShowCreateForm(false)}
              >
                ×
              </button>
            </div>

            <form
              className="project-form"
              onSubmit={handleCreateProject}
            >
              <div className="form-group">
                <label>Project name</label>

                <input
                  name="name"
                  type="text"
                  placeholder="e.g. EcoTrack"
                  required
                  minLength={2}
                />
              </div>

              <div className="form-group">
                <label>Hackathon name</label>

                <input
                  name="hackathon_name"
                  type="text"
                  placeholder="e.g. WhyCode4U Hackathon 2026"
                  required
                  minLength={2}
                />
              </div>

              <div className="form-group">
                <label>Problem statement</label>

                <textarea
                  name="problem_statement"
                  placeholder="What real-world problem are you solving?"
                  required
                />
              </div>

              <div className="form-group">
                <label>Project description</label>

                <textarea
                  name="description"
                  placeholder="Describe your solution and how it works."
                  required
                />
              </div>

              <div className="form-group">
                <label>Technology stack</label>

                <input
                  name="tech_stack"
                  type="text"
                  placeholder="e.g. React, FastAPI, Python, SQLite"
                  required
                />
              </div>

              <div className="form-group">
                <label>Development stage</label>

                <select
                  name="development_stage"
                  required
                  defaultValue="Prototype"
                >
                  <option value="Idea">Idea</option>
                  <option value="Prototype">Prototype</option>
                  <option value="MVP">MVP</option>
                  <option value="Launched">Launched</option>
                </select>
              </div>

              {formError && (
                <p className="form-error">{formError}</p>
              )}

              <div className="form-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setShowCreateForm(false)}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={formSubmitting}
                >
                  {formSubmitting ? "Creating..." : "Create project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="app">
        <main
          className="main-content"
          role="status"
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            padding: "24px",
          }}
        >
          <div
            className="panel"
            style={{ width: "100%", maxWidth: 360, textAlign: "center" }}
          >
            <h2>Loading workspace...</h2>
            <p>Checking your session.</p>
          </div>
        </main>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <AuthScreen />;
  }

  return <Dashboard />;
}

export default App;
