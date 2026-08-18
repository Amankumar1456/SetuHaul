# SetuHaul: Implementation Roadmap & Quick Reference

**Created**: 2026-08-18  
**Status**: Analysis Complete - Ready for Phased Execution  
**Total Effort**: 10 weeks, 8 phases

---

## Executive Summary

SetuHaul is a Transit Management System with a working LLM-based exception handler. The strategy document requires enhancements for **context-aware follow-ups**, **location-based help**, **UI polish**, and **warehouse-centric operations dashboard**.

### Key Gap: No Exception-Type Intelligence
Currently: "Driver has a delay" → generic slot search  
Target: "Driver has mechanical breakdown" → ask repair duration + location, calculate new ETA, move to ON_HOLD if needed

---

## 8-Phase Implementation Timeline

### 🔴 Phase 1: Database Foundation (Weeks 1-2)
**Deliverable**: 10 Application Layers schema  
**Key Tables**: resource_pool, yard_states, driver_location_history, decision_audit  
**Files**: database_migrations/*.sql, database.py (10 layer helpers)

### 🟠 Phase 2: LLM Enhancements (Weeks 2-3)
**Deliverable**: Exception-type detection + dynamic system prompt  
**Key Files**: app/intent_detector.py, agent.py (prompt generation)  
**Logic**: Detect exception type → ask follow-up questions → collect required aspects → execute handler

### 🟡 Phase 3: Location System (Weeks 3-4)
**Deliverable**: GPS capture + ETA recalculation  
**Key Files**: app/routing.py (Geoapify), driver-workspace.tsx (location button)  
**Features**: One-click location share, static fallback for testing, location history cleanup

### 🟢 Phase 4: Chat UX (Weeks 4-5)
**Deliverable**: Streaming responses + rich messages  
**Key Features**: Typing animation, message highlighting, slot options card  
**Tech**: EventSource streaming, React components

### 🔵 Phase 5: Dashboard (Weeks 5-7)
**Deliverable**: Warehouse-centric operations dashboard  
**Sections**: Resource summary, slot timeline, yard snapshot, escalation panel  
**Tech**: Warehouse tabs (A-F), WebSocket real-time updates, manual overrides

### 🟣 Phase 6: Exception Logic (Weeks 6-8)
**Handlers**: Mechanical failure, driver sickness, traffic/checkpoint, facility capacity  
**Key Logic**: Repair duration → new ETA → ON_HOLD if missed; sickness → find replacement driver  
**File**: app/exception_handlers.py

### 💜 Phase 7: Testing (Weeks 8-9)
**Coverage**: Unit tests (intent, allocation), integration (end-to-end), load, scenarios  
**Test Files**: test/test_intent_detection.py, test_exception_handlers.py, test_scenarios.py

### 🤎 Phase 8: Deployment (Weeks 9-10)
**Steps**: Database migration, backend deploy, frontend deploy, smoke tests, ops training

---

## Critical Path (Blocking Dependencies)

```
Start
  ↓
[Phase 1: Database] ← Blocks everything else
  ├→ [Phase 2: LLM] ← Blocks Phase 6
  │  ├→ [Phase 3: Location] ← Blocks ETA accuracy
  │  └→ [Phase 4: UX] ← Can run parallel
  ├→ [Phase 5: Dashboard] ← Blocks Phase 7 testing
  ├→ [Phase 6: Logic] ← Needs Phase 2 + 3
  └→ [Phase 7: Testing]
       ↓
    [Phase 8: Deploy]
```

---

## New Files to Create (37 Total)

### Backend Python (6 files)
```
app/
  ├─ intent_detector.py       [NEW] Exception type classification
  ├─ routing.py               [NEW] Geoapify integration  
  ├─ exception_handlers.py     [NEW] Per-exception business logic
  ├─ agent.py                 [ENHANCE] Dynamic system prompt
  ├─ tools.py                 [ENHANCE] Add location-based tools
  └─ main.py                  [ENHANCE] Streaming + location endpoint
```

### Frontend React (12 files)
```
src/
  ├─ components/setuhaul/
  │  ├─ resource-summary.tsx          [NEW]
  │  ├─ slot-timeline.tsx             [NEW]
  │  ├─ yard-snapshot.tsx             [NEW]
  │  ├─ escalation-panel.tsx          [NEW]
  │  └─ driver-workspace.tsx          [ENHANCE]
  ├─ components/ui/
  │  └─ typing-indicator.tsx          [NEW]
  ├─ hooks/
  │  └─ use-realtime-dashboard.ts     [NEW]
  ├─ lib/
  │  ├─ message-highlighter.ts        [NEW]
  │  ├─ dashboard-realtime.ts         [NEW]
  │  └─ api.ts                        [ENHANCE]
  └─ routes/
     ├─ dashboard.index.tsx           [NEW]
     ├─ dashboard.$warehouseId.tsx    [NEW]
     └─ driver.tsx                    [ENHANCE]
```

### Database & Docs (19 files)
```
database_migrations/
  ├─ 001_create_application_layers.sql    [NEW]
  ├─ 002_add_location_columns.sql         [NEW]
  ├─ 003_seed_initial_data.sql            [NEW]

test/
  ├─ test_intent_detection.py             [NEW]
  ├─ test_exception_handlers.py            [NEW]
  ├─ test_routing.py                      [NEW]
  ├─ test_scenarios.py                    [NEW]
  ├─ test_dashboard_realtime.ts           [NEW]

Docs/
  ├─ COMPREHENSIVE_ANALYSIS_AND_IMPLEMENTATION_PLAN.md  [✅ CREATED]
  ├─ IMPLEMENTATION_ROADMAP.md             [THIS FILE]
  ├─ API_DOCUMENTATION.md                 [NEW]
  ├─ DATABASE_MIGRATION_GUIDE.md          [NEW]
  ├─ OPS_RUNBOOK.md                       [NEW]
  ├─ DRIVER_TESTING_SCENARIOS.md          [NEW]
  └─ DEPLOYMENT_CHECKLIST.md              [NEW]
```

---

## Success Criteria by Phase

| Phase | Metric | Target | Verification |
|-------|--------|--------|---|
| 1 | Database schema completeness | 100% of 10 layers | Schema validation script |
| 2 | Intent detection accuracy | >90% on test set | Unit test with 20+ messages |
| 3 | Location capture success | >95% GPS, 100% fallback | Manual testing with 10 drivers |
| 4 | Streaming latency | <100ms per chunk | Network throttle testing |
| 5 | Dashboard initial load | <2s at 10 concurrent users | Load test with Apache JMeter |
| 6 | Auto-resolution rate | >70% mechanical, >60% sickness | Scenario test coverage |
| 7 | Test coverage | >80% unit, 5+ scenarios | Coverage report |
| 8 | Production stability | 0 critical errors in 24h | Monitoring dashboard |

---

## Decision Checklist

- [ ] **Geoapify API**: Provisioned and API key in .env?
- [ ] **Location Storage**: Delete after booking? (Recommend: YES for privacy)
- [ ] **WebSocket vs Polling**: Use WebSocket for dashboard (recommend YES)
- [ ] **Escalation Levels**: Fixed to LOW/NORMAL/HIGH/CRITICAL? (recommend YES)
- [ ] **Manual Override Approval**: Require supervisor ID? (recommend YES)
- [ ] **Facility Coordinates**: Collected for all 6 warehouses?
- [ ] **Static Locations**: Define WH-A to WH-B midpoint? (for testing)
- [ ] **Message Retention**: How long to keep chat history? (recommend 30 days)
- [ ] **Location Audit**: Log all location accesses for compliance?

---

## Risk Register

| Risk | Severity | Probability | Mitigation |
|------|----------|---|---|
| LLM generates invalid follow-up questions | HIGH | MEDIUM | Use enum lists, add validation |
| Location data breach / privacy violation | CRITICAL | LOW | Opt-in permission, auto-delete |
| Geoapify API quota exceeded | MEDIUM | MEDIUM | Cache routes, fallback to static |
| Database performance degradation | MEDIUM | MEDIUM | Proper indexing, archival strategy |
| Facility capacity mass-update failure | HIGH | LOW | Idempotent logic, transaction rollback |
| WebSocket connection storms | MEDIUM | LOW | Broadcast groups, exponential backoff |

---

## Work Breakdown Structure (WBS)

```
SetuHaul Implementation (10 weeks)
├─ Phase 1: Database (2 weeks) = 40 hours
│  ├─ Schema design & migration scripts = 15 hours
│  ├─ Data model validation = 10 hours
│  ├─ Seed scripts & test fixtures = 15 hours
│
├─ Phase 2: LLM (1.5 weeks) = 30 hours
│  ├─ Intent detector implementation = 12 hours
│  ├─ Dynamic system prompt generation = 10 hours
│  ├─ Multi-turn state management = 8 hours
│
├─ Phase 3: Location (1.5 weeks) = 30 hours
│  ├─ Frontend location capture UI = 12 hours
│  ├─ Geoapify integration & caching = 10 hours
│  ├─ Location history & privacy = 8 hours
│
├─ Phase 4: Chat UX (1.5 weeks) = 30 hours
│  ├─ Streaming architecture & EventSource = 12 hours
│  ├─ Typing animation component = 8 hours
│  ├─ Message highlighting & rich rendering = 10 hours
│
├─ Phase 5: Dashboard (2 weeks) = 40 hours
│  ├─ Warehouse tab navigation = 8 hours
│  ├─ Resource summary component = 10 hours
│  ├─ Slot timeline & yard snapshot = 12 hours
│  ├─ Escalation panel & overrides = 10 hours
│
├─ Phase 6: Exception Logic (2 weeks) = 40 hours
│  ├─ Mechanical failure handler = 10 hours
│  ├─ Driver sickness handler = 10 hours
│  ├─ Traffic/checkpoint handler = 10 hours
│  ├─ Facility capacity handler = 10 hours
│
├─ Phase 7: Testing (1.5 weeks) = 30 hours
│  ├─ Unit tests & mocking = 12 hours
│  ├─ Integration tests = 10 hours
│  ├─ Load & scenario tests = 8 hours
│
└─ Phase 8: Deployment (1 week) = 20 hours
   ├─ Migration & validation = 8 hours
   ├─ Deployment & monitoring = 7 hours
   ├─ Documentation & training = 5 hours
```

**Total Estimated Effort**: ~260 hours = 6.5 weeks of full-time development

---

## Key Implementation Notes

### System Prompt Injection Pattern
```
Base System Prompt (static)
    + Exception-Type Rules (dynamic)
    + Context Snapshot (conversation-aware)
    = Final Prompt sent to LLM
```

### Multi-turn Conversation State (Redis)
```json
{
  "conversation_id": "CONV-ABC123",
  "exception_type": "MECHANICAL_FAILURE",
  "turn_count": 3,
  "aspects_collected": {
    "repair_duration": "2 hours",
    "current_location": {"lat": 18.52, "lng": 73.85}
  },
  "follow_up_needed": ["eta_confirmation"],
  "ttl": 3600
}
```

### Escalation Audit Pattern
Every escalation creates a decision_audit record:
```python
log_decision(
    decision_type="ESCALATION",
    actor_id="AGENT-LLM",
    affected_shipment_id="SHP-12345",
    data={"reason": "No feasible slots", "urgency": "HIGH"},
    previous_state={"status": "IN_TRANSIT"},
    new_state={"status": "ESCALATED"}
)
```

---

## Recommended Team Structure

- **Backend Lead**: 1 engineer (Phases 1, 2, 3, 6, 8)
- **Frontend Lead**: 1 engineer (Phases 4, 5, 8)
- **QA Lead**: 1 engineer (Phases 3-7 throughout)
- **Product Manager**: 0.5 (Phase 5 dashboard specs, decisions)
- **DevOps**: 0.5 (Deployment & monitoring, Phase 8)

**Total**: 4 FTE for 10 weeks

---

## Go-Live Readiness

### Pre-Launch Checklist
- [ ] All 8 phases complete and tested
- [ ] Database migration successful on staging
- [ ] Load test passed (100+ concurrent drivers)
- [ ] Ops team trained on dashboard
- [ ] Runbook documented and reviewed
- [ ] Monitoring alerts configured
- [ ] Rollback plan approved
- [ ] Stakeholder sign-off obtained

### Monitoring Post-Launch
- Track auto-resolution rate by exception type
- Monitor escalation volume and closure time
- Alert on LLM failures or invalid prompts
- Track location capture success rate
- Monitor database query performance

---

## Next Steps

1. **Immediate** (This Week):
   - [ ] Review and approve this analysis
   - [ ] Schedule design review for Phase 1 database
   - [ ] Determine team assignments
   - [ ] Provision Geoapify API key

2. **This Sprint** (Weeks 1-2):
   - [ ] Begin Phase 1: Database schema
   - [ ] Start Phase 2: Intent detector

3. **Following Sprint** (Weeks 3-4):
   - [ ] Complete Phase 1 & 2
   - [ ] Begin Phase 3: Location
   - [ ] Start Phase 4: UX

