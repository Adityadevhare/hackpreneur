import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import "./App.css";
import { useAuth } from "./auth/auth-context";
import AuthScreen from "./auth/AuthScreen";
import { projectsApi } from "./lib/api";
import type {
  HealthResponse,
  Project,
  ProjectCreateData,
  ProjectVisibility,
} from "./lib/api";

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
  const [reloadTrigger, setReloadTrigger] = useState(0);

  // Create project modal state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Selected project state
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const userEmail = user?.email?.trim();
  const displayEmail = userEmail || "Signed-in user";
  const avatarInitial = userEmail?.charAt(0).toUpperCase() || "U";
  const signOutErrorMessage =
    signOutError ??
    (authError ? "Unable to sign out. Please try again." : null);

  const reloadProjects = useCallback(() => {
    setProjectsLoading(true);
    setReloadTrigger((count) => count + 1);
  }, []);

  // Check backend health (unauthenticated probe)
  useEffect(() => {
    let isMounted = true;

    projectsApi
      .getHealth()
      .then((data) => {
        if (isMounted) setBackend(data);
      })
      .catch(() => {
        if (isMounted) setBackend(null);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Load accessible projects using authenticated API client
  useEffect(() => {
    let isMounted = true;

    projectsApi
      .list()
      .then((data) => {
        if (isMounted) {
          setProjects(data);
          setProjectsError(null);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setProjectsError(
            error instanceof Error ? error.message : "Failed to load projects",
          );
        }
      })
      .finally(() => {
        if (isMounted) {
          setProjectsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [reloadTrigger]);

  // Check for unlisted token in URL query string on load
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) return;

    let isMounted = true;
    projectsApi
      .getByToken(token)
      .then((project) => {
        if (isMounted) {
          setSelectedProject(project);
        }
      })
      .catch((err) => {
        console.debug("Unlisted project link resolution failed:", err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Create a new project via authenticated API client
  const handleCreateProject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormSubmitting(true);
    setFormError(null);

    const formData = new FormData(event.currentTarget);

    const projectData: ProjectCreateData = {
      name: (formData.get("name") as string)?.trim() || "",
      hackathon_name: (formData.get("hackathon_name") as string)?.trim() || "",
      problem_statement: (formData.get("problem_statement") as string)?.trim() || "",
      description: (formData.get("description") as string)?.trim() || "",
      tech_stack: (formData.get("tech_stack") as string)?.trim() || "",
      development_stage:
        (formData.get("development_stage") as string) || "Prototype",
      visibility:
        (formData.get("visibility") as ProjectVisibility) || "private",
    };

    try {
      const newProject = await projectsApi.create(projectData);
      setProjects((currentProjects) => [newProject, ...currentProjects]);
      setShowCreateForm(false);
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Failed to create project",
      );
    } finally {
      setFormSubmitting(false);
    }
  };

  // Select project and refresh from server for latest state
  const handleSelectProject = async (project: Project) => {
    setSelectedProject(project);
    setDetailError(null);

    try {
      const fresh = await projectsApi.get(project.id);
      setSelectedProject(fresh);
    } catch (err) {
      console.debug("Background project refresh failed:", err);
    }
  };

  // Return to dashboard overview
  const handleBackToDashboard = () => {
    setSelectedProject(null);
    setDetailError(null);
    setCopiedLink(false);
  };

  // Delete project (owner only)
  const handleDeleteProject = async (projectId: number) => {
    if (
      !window.confirm(
        "Are you sure you want to delete this project? It will be archived and hidden.",
      )
    ) {
      return;
    }

    setActionLoading(true);
    setDetailError(null);

    try {
      await projectsApi.delete(projectId);
      setProjects((current) => current.filter((p) => p.id !== projectId));
      setSelectedProject(null);
    } catch (err) {
      setDetailError(
        err instanceof Error ? err.message : "Failed to delete project",
      );
    } finally {
      setActionLoading(false);
    }
  };

  // Update development stage (owner only)
  const handleUpdateStage = async (newStage: string) => {
    if (!selectedProject) return;

    setActionLoading(true);
    setDetailError(null);

    try {
      const updated = await projectsApi.update(selectedProject.id, {
        development_stage: newStage,
      });
      setSelectedProject(updated);
      setProjects((current) =>
        current.map((p) => (p.id === updated.id ? updated : p)),
      );
    } catch (err) {
      setDetailError(
        err instanceof Error ? err.message : "Failed to update project stage",
      );
    } finally {
      setActionLoading(false);
    }
  };

  // Update visibility (owner only)
  const handleUpdateVisibility = async (newVisibility: ProjectVisibility) => {
    if (!selectedProject) return;

    setActionLoading(true);
    setDetailError(null);

    try {
      const updated = await projectsApi.update(selectedProject.id, {
        visibility: newVisibility,
      });
      setSelectedProject(updated);
      setProjects((current) =>
        current.map((p) => (p.id === updated.id ? updated : p)),
      );
    } catch (err) {
      setDetailError(
        err instanceof Error ? err.message : "Failed to update visibility",
      );
    } finally {
      setActionLoading(false);
    }
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

  // Check if current user is the verified owner of the selected project
  const isOwner = Boolean(
    selectedProject &&
      user?.id &&
      selectedProject.owner_id &&
      selectedProject.owner_id === user.id,
  );

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

                {isOwner && (
                  <button
                    type="button"
                    className="secondary-button"
                    style={{
                      color: "var(--danger)",
                      borderColor: "rgba(239, 68, 68, 0.3)",
                    }}
                    onClick={() => handleDeleteProject(selectedProject.id)}
                    disabled={actionLoading}
                  >
                    {actionLoading ? "Deleting..." : "Delete Project"}
                  </button>
                )}

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
                  <span className="details-label">PROJECT OVERVIEW</span>

                  <h2>{selectedProject.name}</h2>
                  <p>{selectedProject.hackathon_name}</p>
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    flexWrap: "wrap",
                  }}
                >
                  <span className="details-stage">
                    {selectedProject.development_stage}
                  </span>

                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      padding: "6px 10px",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      background: "var(--surface-subtle)",
                      color: "var(--text-secondary)",
                      fontSize: 11,
                      fontWeight: 650,
                      textTransform: "capitalize",
                    }}
                  >
                    {selectedProject.visibility || "private"}
                  </span>
                </div>
              </div>

              {detailError && (
                <p className="form-error" role="alert" style={{ marginBottom: 16 }}>
                  {detailError}
                </p>
              )}

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

              {/* Unlisted sharing link for project owner */}
              {selectedProject.visibility === "unlisted" &&
                selectedProject.unlisted_token && (
                  <div className="details-section">
                    <h3>Unlisted Share Link</h3>
                    <p
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        flexWrap: "wrap",
                      }}
                    >
                      <code
                        style={{
                          padding: "6px 10px",
                          background: "var(--surface-subtle)",
                          border: "1px solid var(--border)",
                          borderRadius: "var(--radius-sm)",
                          fontSize: 11,
                          color: "var(--accent)",
                        }}
                      >
                        {`${window.location.origin}/?token=${selectedProject.unlisted_token}`}
                      </code>

                      <button
                        type="button"
                        className="secondary-button"
                        style={{ minHeight: 30, padding: "0 10px", fontSize: 11 }}
                        onClick={() => {
                          void navigator.clipboard.writeText(
                            `${window.location.origin}/?token=${selectedProject.unlisted_token}`,
                          );
                          setCopiedLink(true);
                          setTimeout(() => setCopiedLink(false), 2000);
                        }}
                      >
                        {copiedLink ? "Copied!" : "Copy Link"}
                      </button>
                    </p>
                  </div>
                )}

              {/* Settings controls for project owner */}
              {isOwner && (
                <div className="details-section">
                  <h3>Project Settings</h3>
                  <div
                    style={{
                      display: "flex",
                      gap: 20,
                      flexWrap: "wrap",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <label
                        style={{
                          display: "block",
                          fontSize: 11,
                          color: "var(--text-muted)",
                          marginBottom: 6,
                          fontWeight: 600,
                        }}
                      >
                        Development Stage
                      </label>
                      <select
                        value={selectedProject.development_stage}
                        onChange={(e) => void handleUpdateStage(e.target.value)}
                        disabled={actionLoading}
                        style={{
                          minHeight: 34,
                          padding: "0 10px",
                          border: "1px solid var(--border-strong)",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--surface-subtle)",
                          color: "var(--text-primary)",
                          fontSize: 12,
                        }}
                      >
                        <option value="Idea">Idea</option>
                        <option value="Prototype">Prototype</option>
                        <option value="MVP">MVP</option>
                        <option value="Launched">Launched</option>
                      </select>
                    </div>

                    <div>
                      <label
                        style={{
                          display: "block",
                          fontSize: 11,
                          color: "var(--text-muted)",
                          marginBottom: 6,
                          fontWeight: 600,
                        }}
                      >
                        Visibility
                      </label>
                      <select
                        value={selectedProject.visibility}
                        onChange={(e) =>
                          void handleUpdateVisibility(
                            e.target.value as ProjectVisibility,
                          )
                        }
                        disabled={actionLoading}
                        style={{
                          minHeight: 34,
                          padding: "0 10px",
                          border: "1px solid var(--border-strong)",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--surface-subtle)",
                          color: "var(--text-primary)",
                          fontSize: 12,
                        }}
                      >
                        <option value="private">Private</option>
                        <option value="unlisted">Unlisted</option>
                        <option value="public">Public</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

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
                <span className="breadcrumb">Workspace / Overview</span>

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
                    <p>Fetching your projects securely from the database.</p>
                  </div>
                ) : projectsError ? (
                  <div className="empty-state">
                    <h3>Unable to load projects</h3>
                    <p role="alert">{projectsError}</p>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={reloadProjects}
                      style={{ marginTop: 12 }}
                    >
                      Try again
                    </button>
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
                        onClick={() => void handleSelectProject(project)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" ||
                            event.key === " "
                          ) {
                            event.preventDefault();
                            void handleSelectProject(project);
                          }
                        }}
                      >
                        <h3>{project.name}</h3>
                        <p>{project.hackathon_name}</p>
                        <p>{project.description}</p>
                        <div
                          style={{
                            display: "flex",
                            gap: 8,
                            alignItems: "center",
                            marginTop: 10,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--text-muted)",
                            }}
                          >
                            {project.development_stage}
                          </span>
                          <span
                            style={{
                              fontSize: 10,
                              color: "var(--border-strong)",
                            }}
                          >
                            •
                          </span>
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--accent)",
                              textTransform: "capitalize",
                              fontWeight: 600,
                            }}
                          >
                            {project.visibility || "private"}
                          </span>
                        </div>
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
              onSubmit={(e) => void handleCreateProject(e)}
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

              <div className="form-group">
                <label>Visibility</label>

                <select
                  name="visibility"
                  required
                  defaultValue="private"
                >
                  <option value="private">
                    Private (Only you can access)
                  </option>
                  <option value="unlisted">
                    Unlisted (Shareable via link)
                  </option>
                  <option value="public">
                    Public (Visible to all hackathon members)
                  </option>
                </select>
              </div>

              {formError && (
                <p className="form-error" role="alert">
                  {formError}
                </p>
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
