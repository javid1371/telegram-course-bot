# 📝 Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Phase 4 - Polish & Optimization (Planned)
- [ ] Redis caching integration
- [ ] Advanced rate limiting with Redis
- [ ] Jalali calendar support
- [ ] Multi-language support
- [ ] Comprehensive test suite

## [0.3.2] - 2026-02-25

### Cross-Platform Sync — Phase 3 (Complete) ✅

#### Added
- **Alembic migration** for `sync_events` and `sync_user_snapshots` tables (merge of two heads)
- **Admin sync monitor panel** (🔄 سینک پلتفرم) — live dashboard with:
  - Peer server connectivity check
  - Event counts by status (pending/synced/failed/skipped)
  - Snapshot counts (total/applied/waiting)
  - Manual retry button for pending events
- **Deployment documentation** for dual-server (Telegram + Bale) setup with sync

#### Changed
- Updated `SyncEvent.status` default from `'logged'` to `'pending'` — events are now queued for push immediately
- Removed Phase 1 monitor-only comments from `SyncEvent` model
- Updated PROJECT_STATUS.md to reflect cross-platform sync completion

#### Summary: 3-Phase Cross-Platform Sync
| Phase | Commit | Description |
|-------|--------|-------------|
| Phase 1 | `87f11ed` | Event monitor — log sync events (fire-and-forget) |
| Phase 2 | `0d130bd` | Bidirectional sync — push/receive + shadow profiles |
| Phase 3 | this release | Migration + admin UI + deployment docs |

## [0.3.1] - 2025-07-14

### n8n Workflow v8 - Critical CRM Bug Fixes

#### Fixed
- **Critical: Didar CRM search result parsing** — All 7 Code nodes used `Response.List` but Didar `search` operation returns `search_respons.List`. This caused:
  - Register path: Always created duplicate persons → "Duplicate contacts" error
  - Lesson path: Person not found → no deal stage updates
  - Form path: Person not found → no field updates
  - Complete path: Person not found → no completion processing
  - Deal paths: Deals never searched → never updated
- All 7 nodes now use `search_respons.List` with `Response.List` fallback for robustness

#### Added
- **Form → Note**: Form responses now saved as a note (یادداشت) in Didar CRM with formatted text (📋 title + bullet-point answers)
- New `Create Note Form` Didar CRM node in form submission path

## [0.3.0] - 2026-02-10

### Phase 3 - Admin Panel ✅

#### Added
- Full admin panel with dashboard statistics
- Lesson management (CRUD: add, edit, delete, toggle, reorder)
- User management (list, search, view, block, delete, reset progress)
- Registration fields management (dynamic field creation: text, number, email, phone, date, select)
- Broadcast messaging system (to all, active, inactive, completed, by tag)
- Private messaging to individual users
- Tag management for users
- Webhook management (add, list, test webhooks)
- Analytics & reporting (today, week, month, all-time stats)
- Excel export (users, progress, analytics)
- Settings overview panel

## [0.2.0] - 2026-02-10

### Phase 2 - Core Bot Features ✅

#### Added
- Admin authentication system with `@admin_only` decorator
- Dynamic user registration with FSM (Finite State Machine)
  - Support for text, number, email, phone, date, select field types
  - Input validation per field type
  - Campaign tracking via start parameters
  - Referral code system
- Lesson delivery system
  - Support for text, video, audio, document, photo content types
  - Automatic lesson progression
  - Call to Action (CTA) buttons
- Progress tracking and confirmation
  - Visual progress bar
  - Lesson completion confirmation
  - Course completion detection
- Webhook integration for events (user_registered, lesson_completed, course_completed)
- Service layer architecture:
  - UserService - user CRUD and registration
  - LessonService - lesson management and delivery
  - WebhookService - outgoing webhook notifications
  - BroadcastService - mass messaging with rate limiting
  - AnalyticsService - statistics and reporting
  - ExportService - Excel export functionality
  - ReminderService - inactive user reminders
- Task scheduler (APScheduler):
  - Daily reminders for inactive users (10:00 AM)
  - Daily statistics snapshot (23:55)
  - Scheduled message processing (every 5 min)
- User commands: /start, /help, /progress
- Menu-based navigation for users

## [0.1.0] - 2026-02-09

### Phase 1 - Infrastructure Setup ✅

#### Added
- Project structure and directory layout
- Database models with SQLAlchemy
  - Admin model
  - User model with dynamic registration data
  - Lesson model with multiple content types
  - UserProgress tracking
  - WebhookSetting for flexible configuration
  - Campaign tracking
  - ScheduledMessage for reminders
  - BroadcastLog for mass messaging tracking
  - DailyStat for analytics
- Configuration management (config.py)
- Environment variables support (.env)
- Docker and Docker Compose setup
- PostgreSQL integration
- Redis support (optional)
- Alembic for database migrations
- Utility functions:
  - Validators for email, phone, date, etc.
  - Keyboard layouts (user and admin)
  - Decorators for access control
  - Helper functions
- Logging system
- Requirements.txt with all dependencies
- Comprehensive README.md
- Deployment guide (DEPLOYMENT.md)
- Git repository initialization

#### Infrastructure
- Python 3.11+ support
- Async/await architecture with aiogram 3.x
- PostgreSQL 15+ database
- Redis for caching (optional)
- Docker containerization
- Systemd service support

#### Documentation
- Installation guide
- Deployment instructions
- Server setup guide
- Docker deployment guide
- Troubleshooting section

---

## Version History

- **v0.3.0** (2026-02-10): Admin panel and management features
- **v0.2.0** (2026-02-10): Core bot features (registration, lessons, progress)
- **v0.1.0** (2026-02-09): Initial infrastructure setup
- More versions coming with each phase completion...

## Roadmap

### ✅ Phase 1: Infrastructure Setup (Complete)
- [x] Project structure
- [x] Database models
- [x] Docker setup
- [x] Configuration
- [x] Utilities

### ✅ Phase 2: Core Bot Features (Complete)
- [x] Admin authentication
- [x] User registration (FSM)
- [x] Lesson delivery
- [x] Progress tracking
- [x] Webhook integration

### ✅ Phase 3: Admin Panel (Complete)
- [x] Lesson management (CRUD)
- [x] User management
- [x] Registration fields
- [x] Broadcast system
- [x] Webhook settings
- [x] Analytics & Export

### 🎯 Phase 4: Polish & Optimization (Planned)
- [ ] Redis caching
- [ ] Advanced rate limiting
- [ ] Jalali calendar
- [ ] Multi-language
- [ ] Test suite

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details
