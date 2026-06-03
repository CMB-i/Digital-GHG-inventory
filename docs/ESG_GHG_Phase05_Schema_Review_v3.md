ESG / GHG Platform  |  Phase 0.5 Schema Review v3  |  CONFIDENTIAL	**DRAFT — AWAITING SIGN-OFF**

**ESG / GHG Data Governance Platform**

**PHASE 0.5 — Schema Design Review**

*v3 — All corrections applied*

*For Team Sign-Off Before Phase 1 Migrations*

|**Version**|v3 — Schema Review (Post v2 Corrections)|
| :- | :- |
|**Date**|June 2026|
|**Status**|AWAITING TEAM SIGN-OFF — DO NOT START MIGRATIONS|
|**Changes from v2**|users.archetype removed · sites.company\_name added · value\_set\_versions approval workflow added · field\_type=file added · proof\_documents.field\_id confirmed nullable · 'Super Admin only' replaced with 'user with required permission' throughout|
|**Linked PRD**|PRD v3.0 (primary) + PRD v3.1 Addendum|
|**Linked Plan**|Build Plan v3.1|
|**AI Align**|AI Alignment v2.1|

**STOP. No migration file may be written until all sign-off boxes in Section 20 are ticked and the team lead confirms approval on WhatsApp.**


# **1. Purpose and Scope**
This is v3 of the Phase 0.5 schema review, incorporating all corrections raised after v2. It is the version to be signed off before Phase 1 migration writing begins.

### **What changed from v2**

|**[x]**|users.archetype removed entirely. users is now identity/auth only. access\_matrix is the sole source of truth for what a user can do.|
| :-: | :- |
|**[x]**|sites.company\_name VARCHAR(255) NULL added. Nullable because not all sites will have complete company mapping data during MVP.|
|**[x]**|value\_set\_versions: approval workflow added. New columns: status, submitted\_by, submitted\_at, approved\_by, approved\_at, rejected\_by, rejected\_at, rejection\_reason. State machine: Draft → Submitted → Approved / Rejected. Rejected → Draft after corrections.|
|**[x]**|Rule added: only Approved value\_set\_versions may be used in published forms and calculations.|
|**[x]**|field\_versions.field\_type enum: file added. table remains deferred.|
|**[x]**|proof\_documents.field\_id confirmed nullable. Nullable supports both field-level and submission-level proof uploads without schema change.|
|**[x]**|All occurrences of 'Super Admin only' replaced with 'user with required permission'. All access is governed by access\_matrix only.|

**Stack: Flask · PostgreSQL · Alembic direct (no Flask-Migrate) · venv dev · Waitress · Monthly standalone submissions = MVP.**

# **2. MVP Table List**

|**Table**|**Module**|**Mig #**|**Purpose**|
| :- | :- | :- | :- |
|users|USRMGMT|001|Platform users — identity and auth only. No archetype.|
|sites|SITEMST|002|Physical sites / facilities (includes company\_name)|
|access\_matrix|ACCESS|003|All permission rows — sole source of truth for auth|
|forms|FORMBLD|004|Form header|
|form\_versions|FORMBLD|004|Immutable form snapshots|
|fields|FORMBLD|004|Field definitions|
|field\_versions|FORMBLD|004|Immutable field snapshots (config JSONB, field\_type includes file)|
|formulas|FRMULA|005|Named formula definitions|
|formula\_versions|FRMULA|005|Versioned expressions + token JSONB|
|value\_sets|VALSET|005|Named lookup sets|
|value\_set\_entries|VALSET|005|Entries within a value set version|
|value\_set\_versions|VALSET|005|Versioned value set snapshots — own approval workflow|
|workflows|WFLWBLD|006|Named workflow definitions|
|workflow\_versions|WFLWBLD|006|Versioned workflow snapshots|
|workflow\_levels|WFLWBLD|006|Ordered approval levels|
|workflow\_level\_approvers|WFLWBLD|006|Approvers per level (+ sequence\_number)|
|reporting\_periods|PERIOD|007|Monthly periods per site|
|submissions|SUBMIT|008|Submission header — one per site+form+period|
|submission\_values|SUBMIT|008|EAV rows — one per field per submission|
|approval\_actions|APPROV|009|Approve / reject / changes-requested records|
|issues|APPROV|009|Raised issues blocking final approval|
|issue\_comments|APPROV|009|Threaded comments on issues|
|notifications|NOTIFY|010|In-app notifications|
|proof\_documents|SUBMIT|010|Proof file metadata — field\_id nullable (field-level or submission-level)|
|report\_templates|RPTBLD|011|Report template configs for Excel export|
|app\_config|SYSTEM|012|Configurable platform settings (e.g. financial\_year\_start\_month)|

# **3. Deferred / Future Tables**

|**Table / Feature**|**Reason Deferred**|
| :- | :- |
|regions|Pilot is site-level only. region\_id not on sites in MVP. scope\_type = global / site only.|
|audit\_log|Full audit log (old/new value, viewer UI). AUDITL folder stub only. Lifecycle cols + formula\_inputs\_snapshot are the MVP substitute.|
|revision\_submissions|Revision workflow UI deferred. parent\_submission\_id nullable on submissions reserved.|
|quarterly / annual tables|Aggregated views over approved monthly data — not separate tables.|
|scheduler\_jobs|APScheduler deadline/overdue job — conditional on confirmation.|
|whatsapp\_sms\_log|WhatsApp / SMS channels deferred. notifications.channel col keeps sms in enum.|
|field\_type = table|Table-type fields deferred to v2. field\_config JSONB schema supports it without column changes.|

# **4. Column Definitions per MVP Table**
**Lifecycle + soft-delete columns appear on every table. Listed once in the legend below — not repeated per table.**

### **Lifecycle / Soft-Delete Legend (applies to all tables unless noted)**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|created\_at|TIMESTAMP|NO|now()|Row creation time (UTC)|
|created\_by|INTEGER|NO|—|FK → users.id|
|updated\_at|TIMESTAMP|NO|now()|Last update time (UTC)|
|updated\_by|INTEGER|YES|NULL|FK → users.id|
|is\_deleted|BOOLEAN|NO|false|Soft-delete flag|
|deleted\_at|TIMESTAMP|YES|NULL|Set on soft-delete|
|deleted\_by|INTEGER|YES|NULL|FK → users.id|
|delete\_reason|TEXT|YES|NULL|Mandatory in service layer even though nullable in schema|

## **4.1  users**
**v3: archetype removed. users is identity/auth only. access\_matrix is the sole source of truth for permissions.**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|email|VARCHAR(255)|NO|—|UNIQUE. Login identifier.|
|password\_hash|VARCHAR(255)|NO|—|bcrypt hash. Never plaintext.|
|full\_name|VARCHAR(255)|NO|—|Display name|
|is\_active|BOOLEAN|NO|true|Inactive users cannot log in|
|last\_login\_at|TIMESTAMP|YES|NULL|Informational only|
|phone|VARCHAR(50)|YES|NULL|Reserved for future SMS/WhatsApp channel|
|...lifecycle|(legend)|—|—|created\_at/by, updated\_at/by, soft-delete cols|

## **4.2  sites**
**v3: company\_name VARCHAR(255) NULL added. regions deferred — no region\_id in MVP.**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|UNIQUE site name|
|code|VARCHAR(50)|NO|—|Short site code — UNIQUE|
|company\_name|VARCHAR(255)|YES|NULL|Company this site belongs to. Nullable — mapping may be incomplete during MVP.|
|description|TEXT|YES|NULL|Optional|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.3  access\_matrix**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|user\_id|INTEGER|NO|—|FK → users.id|
|scope\_type|VARCHAR(20)|NO|—|ENUM: global / site  (region deferred)|
|scope\_site\_id|INTEGER|YES|NULL|FK → sites.id. NULL when scope\_type = global.|
|scope\_region\_id|INTEGER|YES|NULL|Reserved — always NULL in MVP.|
|entity\_type|VARCHAR(50)|NO|—|e.g. form / workflow / submission|
|entity\_id|INTEGER|YES|NULL|NULL = applies to all entities of that type in scope|
|can\_view|BOOLEAN|NO|false||
|can\_create|BOOLEAN|NO|false||
|can\_edit|BOOLEAN|NO|false||
|can\_delete|BOOLEAN|NO|false|Soft-delete only|
|can\_submit|BOOLEAN|NO|false|SPOC submission permission|
|can\_approve|BOOLEAN|NO|false||
|can\_reject|BOOLEAN|NO|false||
|can\_reopen|BOOLEAN|NO|false||
|can\_export|BOOLEAN|NO|false||
|can\_manage\_forms|BOOLEAN|NO|false|Form builder access|
|can\_manage\_users|BOOLEAN|NO|false|User management — 11th flag|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

**Service validation: scope\_type=global → both scope\_site\_id and scope\_region\_id must be NULL. scope\_type=site → scope\_site\_id must be set.**

## **4.4  forms**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|Human-readable name|
|code|VARCHAR(50)|NO|—|UNIQUE stable code|
|description|TEXT|YES|NULL|Optional|
|current\_version\_id|INTEGER|YES|NULL|FK → form\_versions.id. NULL until first publish.|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.5  form\_versions**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|form\_id|INTEGER|NO|—|FK → forms.id|
|version\_number|INTEGER|NO|—|Monotonically increasing per form. Never reused.|
|status|VARCHAR(30)|NO|'Draft'|ENUM: Draft / Published / Archived|
|published\_at|TIMESTAMP|YES|NULL|Set when Published|
|published\_by|INTEGER|YES|NULL|FK → users.id|
|notes|TEXT|YES|NULL|Change notes|
|...lifecycle|(legend)|—|—|created\_at/by only — immutable once published|

## **4.6  fields**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|form\_id|INTEGER|NO|—|FK → forms.id|
|field\_code|VARCHAR(100)|NO|—|UNIQUE per form. Stable — never changes.|
|display\_order|INTEGER|NO|—|Ordering within form|
|current\_version\_id|INTEGER|YES|NULL|FK → field\_versions.id|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.7  field\_versions**
**v3: field\_type enum updated — file added. table remains deferred.**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|field\_id|INTEGER|NO|—|FK → fields.id|
|version\_number|INTEGER|NO|—|Monotonically increasing per field|
|field\_name|VARCHAR(255)|NO|—|Display label — may change between versions|
|field\_type|VARCHAR(50)|NO|—|ENUM: text / number / dropdown / date / calculated / file.  table deferred.|
|field\_config|JSONB|NO|'{}'|Unit, min, max, formula\_version\_id, value\_set\_version\_id, is\_required, help\_text, accepted\_mime\_types (for file type), etc.|
|form\_version\_id|INTEGER|NO|—|FK → form\_versions.id — snapshot binding|
|...lifecycle|(legend)|—|—|created\_at/by only — immutable once published|

## **4.8  formulas**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|Human-readable name|
|code|VARCHAR(100)|NO|—|UNIQUE stable code|
|current\_version\_id|INTEGER|YES|NULL|FK → formula\_versions.id|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.9  formula\_versions**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|formula\_id|INTEGER|NO|—|FK → formulas.id|
|version\_number|INTEGER|NO|—|Monotonically increasing|
|expression|TEXT|NO|—|simpleeval-compatible expression string|
|tokens|JSONB|NO|'{}'|Variable map: token → field\_code|
|published\_at|TIMESTAMP|YES|NULL|Set when published|
|published\_by|INTEGER|YES|NULL|FK → users.id|
|...lifecycle|(legend)|—|—|created\_at/by only — immutable once published|

## **4.10  value\_sets**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|Display name|
|code|VARCHAR(100)|NO|—|UNIQUE stable code|
|current\_version\_id|INTEGER|YES|NULL|FK → value\_set\_versions.id — points to current Approved version|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.11  value\_set\_versions**
**v3: approval workflow added. Emission factors/constants directly affect calculations — Approved versions only may be used in published forms.**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|value\_set\_id|INTEGER|NO|—|FK → value\_sets.id|
|version\_number|INTEGER|NO|—|Monotonically increasing|
|status|VARCHAR(30)|NO|'Draft'|ENUM: Draft / Submitted / Approved / Rejected|
|effective\_from|DATE|NO|—|Admin-set date; defaults to approval date if not specified|
|effective\_to|DATE|YES|NULL|NULL = currently active Approved version|
|submitted\_by|INTEGER|YES|NULL|FK → users.id — set when status → Submitted|
|submitted\_at|TIMESTAMP|YES|NULL|Set when status → Submitted|
|approved\_by|INTEGER|YES|NULL|FK → users.id — set when status → Approved|
|approved\_at|TIMESTAMP|YES|NULL|Set when status → Approved|
|rejected\_by|INTEGER|YES|NULL|FK → users.id — set when status → Rejected|
|rejected\_at|TIMESTAMP|YES|NULL|Set when status → Rejected|
|rejection\_reason|TEXT|YES|NULL|Mandatory in service layer when status → Rejected|
|...lifecycle|(legend)|—|—|created\_at/by only — immutable once Approved|

**Rule: only value\_set\_versions with status = Approved may be referenced in published form field\_config or used in formula calculations. Service layer enforces this at publish time.**

## **4.12  value\_set\_entries**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|value\_set\_version\_id|INTEGER|NO|—|FK → value\_set\_versions.id|
|entry\_code|VARCHAR(100)|NO|—|Stable code — stored in submission\_values.raw\_value|
|entry\_label|VARCHAR(255)|NO|—|Display label — may change in new versions|
|display\_order|INTEGER|NO|—|Sort order in dropdown|
|is\_active|BOOLEAN|NO|true|Inactive entries hidden in UI; historical submissions preserved|

## **4.13  workflows**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|Display name|
|code|VARCHAR(100)|NO|—|UNIQUE stable code|
|current\_version\_id|INTEGER|YES|NULL|FK → workflow\_versions.id|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.14  workflow\_versions**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|workflow\_id|INTEGER|NO|—|FK → workflows.id|
|version\_number|INTEGER|NO|—|Monotonically increasing|
|published\_at|TIMESTAMP|YES|NULL|Set when published|
|published\_by|INTEGER|YES|NULL|FK → users.id|
|notes|TEXT|YES|NULL|Change log|
|...lifecycle|(legend)|—|—|created\_at/by only — immutable once published|

## **4.15  workflow\_levels**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|workflow\_version\_id|INTEGER|NO|—|FK → workflow\_versions.id|
|level\_number|INTEGER|NO|—|1-based ordering|
|level\_name|VARCHAR(100)|NO|—|Display label e.g. 'Level 1 — Site Manager'|
|approval\_mode|VARCHAR(30)|NO|—|ENUM: ANY\_ONE / SEQUENTIAL / ALL\_REQUIRED / MAJORITY. MVP builds ANY\_ONE + SEQUENTIAL.|

## **4.16  workflow\_level\_approvers**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|workflow\_level\_id|INTEGER|NO|—|FK → workflow\_levels.id|
|user\_id|INTEGER|NO|—|FK → users.id|
|sequence\_number|INTEGER|YES|NULL|Required for SEQUENTIAL mode (1-based). NULL for ANY\_ONE.|

**Service validation: SEQUENTIAL level → all approvers must have non-null sequence\_number. ANY\_ONE → sequence\_number must be NULL.**

## **4.17  reporting\_periods**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|site\_id|INTEGER|NO|—|FK → sites.id|
|year|INTEGER|NO|—|Financial year e.g. 2025 for FY 2025-26|
|month|INTEGER|NO|—|1–12 calendar month|
|status|VARCHAR(30)|NO|'OPEN'|ENUM: OPEN / SUBMISSION\_CLOSED / LOCKED / REOPENED|
|deadline|DATE|YES|NULL|Submission deadline|
|reopen\_reason|TEXT|YES|NULL|Mandatory when status = REOPENED|
|reopened\_at|TIMESTAMP|YES|NULL|Set when period is reopened|
|reopened\_by|INTEGER|YES|NULL|FK → users.id — user with can\_reopen permission|
|...lifecycle|(legend)|—|—|created\_at/by, updated\_at/by, soft-delete cols|

## **4.18  submissions**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|site\_id|INTEGER|NO|—|FK → sites.id|
|form\_id|INTEGER|NO|—|FK → forms.id|
|form\_version\_id|INTEGER|NO|—|FK → form\_versions.id — locked at creation. Never auto-migrated.|
|reporting\_period\_id|INTEGER|NO|—|FK → reporting\_periods.id|
|workflow\_version\_id|INTEGER|NO|—|FK → workflow\_versions.id — locked at creation.|
|status|VARCHAR(30)|NO|'Draft'|Submission status enum — see §18|
|submitted\_by|INTEGER|YES|NULL|FK → users.id. Set on first submit.|
|submitted\_at|TIMESTAMP|YES|NULL|Set on first submit|
|approved\_by|INTEGER|YES|NULL|FK → users.id. Set when final approval granted.|
|approved\_at|TIMESTAMP|YES|NULL|Set when final approval granted.|
|is\_locked|BOOLEAN|NO|false|True when status = Approved. Checked on ALL write paths.|
|last\_status\_changed\_at|TIMESTAMP|YES|NULL|Updated on every status transition.|
|current\_level|INTEGER|YES|NULL|Current approval level (1-based). NULL if not yet submitted.|
|parent\_submission\_id|INTEGER|YES|NULL|FK → submissions.id. NULL in MVP. Reserved for future revision workflow.|
|anomaly\_flag|BOOLEAN|NO|false|Set if any field value triggers anomaly detection|
|anomaly\_notes|TEXT|YES|NULL|Explanation when anomaly\_flag = true|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols. is\_locked prevents edits even if is\_deleted = false.|

## **4.19  submission\_values (EAV)**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|submission\_id|INTEGER|NO|—|FK → submissions.id|
|field\_id|INTEGER|NO|—|FK → fields.id|
|field\_version\_id|INTEGER|NO|—|FK → field\_versions.id — exact version in effect at submission|
|raw\_value|TEXT|YES|NULL|User-entered value as text. For file fields: storage\_key of the proof\_document.|
|calculated\_value|NUMERIC|YES|NULL|Resolved numeric value for calculated fields|
|formula\_version\_id|INTEGER|YES|NULL|FK → formula\_versions.id — snapshotted at eval time|
|value\_set\_version\_id|INTEGER|YES|NULL|FK → value\_set\_versions.id — snapshotted at eval time. Must be Approved.|
|formula\_inputs\_snapshot|JSONB|YES|NULL|Raw inputs used in formula eval — immutable MVP audit trail|
|formula\_eval\_at|TIMESTAMP|YES|NULL|When formula was last evaluated|
|...lifecycle|(legend)|—|—|created\_at/by, updated\_at/by (no soft-delete on values)|

## **4.20  approval\_actions**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|submission\_id|INTEGER|NO|—|FK → submissions.id|
|actor\_id|INTEGER|NO|—|FK → users.id — must not equal submissions.submitted\_by|
|level\_number|INTEGER|NO|—|Approval level this action applies to|
|action|VARCHAR(30)|NO|—|ENUM: Approved / Rejected / Changes\_Requested / Raised\_Issue|
|comment|TEXT|YES|NULL|Mandatory for Changes\_Requested and Rejected in service layer|
|acted\_at|TIMESTAMP|NO|now()|When action was taken|

## **4.21  issues**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|submission\_id|INTEGER|NO|—|FK → submissions.id|
|raised\_by|INTEGER|NO|—|FK → users.id|
|title|VARCHAR(255)|NO|—|Short title|
|description|TEXT|NO|—|Full issue description|
|status|VARCHAR(30)|NO|'Open'|ENUM: Open / Responded / Resolved / Closed / Reopened|
|resolved\_by|INTEGER|YES|NULL|FK → users.id|
|resolved\_at|TIMESTAMP|YES|NULL|When resolved|
|blocks\_approval|BOOLEAN|NO|true|True = final approval blocked until Resolved or Closed|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.22  issue\_comments**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|issue\_id|INTEGER|NO|—|FK → issues.id|
|author\_id|INTEGER|NO|—|FK → users.id|
|body|TEXT|NO|—|Comment text|
|posted\_at|TIMESTAMP|NO|now()|When posted|

## **4.23  notifications**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|user\_id|INTEGER|NO|—|FK → users.id — recipient|
|event\_type|VARCHAR(100)|NO|—|e.g. submission\_submitted / approval\_approved / changes\_requested / value\_set\_rejected|
|entity\_type|VARCHAR(50)|NO|—|e.g. submission / issue / value\_set\_version|
|entity\_id|INTEGER|NO|—|ID of the related entity|
|message|TEXT|NO|—|Rendered notification text|
|channel|VARCHAR(30)|NO|'in\_app'|ENUM: in\_app / email / sms. MVP delivers in\_app only.|
|is\_read|BOOLEAN|NO|false|Marked true when user views notification|
|read\_at|TIMESTAMP|YES|NULL|When read|
|created\_at|TIMESTAMP|NO|now()|Minimal lifecycle — no soft-delete on notifications|

## **4.24  proof\_documents**
**v3: field\_id nullable confirmed. Supports both field-level proofs (file field type) and submission-level proofs without schema change.**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|submission\_id|INTEGER|NO|—|FK → submissions.id|
|field\_id|INTEGER|YES|NULL|FK → fields.id — NULL for submission-level proofs. Set for field-level (field\_type=file).|
|original\_name|VARCHAR(255)|NO|—|Original file name for display|
|storage\_key|TEXT|NO|—|MinIO/S3 object key — never the file itself in DB|
|mime\_type|VARCHAR(100)|NO|—|e.g. application/pdf, image/jpeg|
|file\_size\_bytes|INTEGER|NO|—|Bytes|
|uploaded\_by|INTEGER|NO|—|FK → users.id|
|uploaded\_at|TIMESTAMP|NO|now()|Upload timestamp|
|...lifecycle|(legend)|—|—|Soft-delete cols only|

## **4.25  report\_templates**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|name|VARCHAR(255)|NO|—|Display name|
|code|VARCHAR(100)|NO|—|UNIQUE stable code|
|description|TEXT|YES|NULL|Optional|
|scope\_type|VARCHAR(20)|YES|NULL|ENUM: global / site. NULL = applies everywhere.|
|scope\_site\_id|INTEGER|YES|NULL|FK → sites.id. NULL when scope\_type = global.|
|config\_json|JSONB|NO|'{}'|Column list, field codes, ordering, grouping, filters for Excel export|
|...lifecycle|(legend)|—|—|Soft-delete + lifecycle cols|

## **4.26  app\_config**

|**Column**|**Type**|**Null?**|**Default**|**Notes**|
| :- | :- | :- | :- | :- |
|id|SERIAL|NO|auto|Primary key|
|config\_key|VARCHAR(100)|NO|—|UNIQUE. e.g. financial\_year\_start\_month|
|config\_value|TEXT|NO|—|Stored as text; parsed by type in service layer|
|config\_type|VARCHAR(30)|NO|—|ENUM: integer / string / boolean / json|
|description|TEXT|YES|NULL|Human-readable explanation for settings UI|
|updated\_by|INTEGER|YES|NULL|FK → users.id — user with settings permission who last changed this|
|updated\_at|TIMESTAMP|NO|now()|Last update time|

**No soft-delete on app\_config — rows updated in place. Seed row: financial\_year\_start\_month = '4', type = integer.**

# **5. Primary Keys**
All 26 tables use SERIAL (auto-incrementing integer) as primary key.

# **6. Foreign Keys — Summary**

|**Column**|**References**|**Notes**|
| :- | :- | :- |
|access\_matrix.user\_id|users.id||
|access\_matrix.scope\_site\_id|sites.id|Nullable — NULL for global scope|
|access\_matrix.scope\_region\_id|(reserved)|Always NULL in MVP|
|forms.current\_version\_id|form\_versions.id|Nullable until first publish|
|form\_versions.form\_id|forms.id||
|fields.form\_id|forms.id||
|fields.current\_version\_id|field\_versions.id|Nullable until first publish|
|field\_versions.field\_id|fields.id||
|field\_versions.form\_version\_id|form\_versions.id|Snapshot binding|
|formula\_versions.formula\_id|formulas.id||
|value\_sets.current\_version\_id|value\_set\_versions.id|Points to current Approved version|
|value\_set\_versions.value\_set\_id|value\_sets.id||
|value\_set\_versions.submitted\_by|users.id|Nullable|
|value\_set\_versions.approved\_by|users.id|Nullable|
|value\_set\_versions.rejected\_by|users.id|Nullable|
|value\_set\_entries.value\_set\_version\_id|value\_set\_versions.id||
|workflow\_versions.workflow\_id|workflows.id||
|workflow\_levels.workflow\_version\_id|workflow\_versions.id||
|workflow\_level\_approvers.workflow\_level\_id|workflow\_levels.id||
|workflow\_level\_approvers.user\_id|users.id||
|reporting\_periods.site\_id|sites.id||
|reporting\_periods.reopened\_by|users.id|Nullable — user with can\_reopen permission|
|submissions.site\_id|sites.id||
|submissions.form\_id|forms.id||
|submissions.form\_version\_id|form\_versions.id|Locked at creation|
|submissions.reporting\_period\_id|reporting\_periods.id||
|submissions.workflow\_version\_id|workflow\_versions.id|Locked at creation|
|submissions.submitted\_by|users.id|Nullable|
|submissions.approved\_by|users.id|Nullable|
|submissions.parent\_submission\_id|submissions.id|Self-ref. NULL in MVP.|
|submission\_values.submission\_id|submissions.id||
|submission\_values.field\_id|fields.id||
|submission\_values.field\_version\_id|field\_versions.id|Snapshot|
|submission\_values.formula\_version\_id|formula\_versions.id|Nullable|
|submission\_values.value\_set\_version\_id|value\_set\_versions.id|Nullable — must be Approved version|
|approval\_actions.submission\_id|submissions.id||
|approval\_actions.actor\_id|users.id|actor ≠ submitted\_by enforced in Flask|
|issues.submission\_id|submissions.id||
|issue\_comments.issue\_id|issues.id||
|notifications.user\_id|users.id||
|proof\_documents.submission\_id|submissions.id||
|proof\_documents.field\_id|fields.id|Nullable — NULL for submission-level proofs|
|report\_templates.scope\_site\_id|sites.id|Nullable|
|app\_config.updated\_by|users.id|Nullable|

# **7. Enums / Status Values**
### **Stored as VARCHAR — validated in Flask service layer. No PostgreSQL ENUM type.**

|**Column**|**Values**|**Notes**|
| :- | :- | :- |
|access\_matrix.scope\_type|global / site|region deferred. scope\_region\_id col reserved but always NULL in MVP.|
|form\_versions.status|Draft / Published / Archived|One Published version per form at a time|
|field\_versions.field\_type|text / number / dropdown / date / calculated / file|table deferred to v2|
|value\_set\_versions.status|Draft / Submitted / Approved / Rejected|Own approval cycle — see §12|
|reporting\_periods.status|OPEN / SUBMISSION\_CLOSED / LOCKED / REOPENED|See §13 for transitions|
|submissions.status|Draft / Submitted / Under\_Review / Changes\_Requested / Resubmitted / Approved / Rejected|See §18 for state machine|
|workflow\_levels.approval\_mode|ANY\_ONE / SEQUENTIAL / ALL\_REQUIRED / MAJORITY|MVP builds ANY\_ONE + SEQUENTIAL only|
|approval\_actions.action|Approved / Rejected / Changes\_Requested / Raised\_Issue||
|issues.status|Open / Responded / Resolved / Closed / Reopened|Open issues block final approval|
|notifications.channel|in\_app / email / sms|MVP delivers in\_app only|
|app\_config.config\_type|integer / string / boolean / json|Parsing hint for service layer|
|report\_templates.scope\_type|global / site|Mirrors access\_matrix scope logic|

# **8. Unique Constraints**

|**Type**|**Name**|**Definition**|
| :- | :- | :- |
|UNIQUE|uq\_users\_email|users(email)|
|UNIQUE|uq\_sites\_name|sites(name)|
|UNIQUE|uq\_sites\_code|sites(code)|
|UNIQUE|uq\_forms\_code|forms(code)|
|UNIQUE|uq\_fields\_code\_per\_form|fields(form\_id, field\_code)|
|UNIQUE|uq\_formula\_code|formulas(code)|
|UNIQUE|uq\_value\_set\_code|value\_sets(code)|
|UNIQUE|uq\_workflow\_code|workflows(code)|
|UNIQUE|uq\_period\_site\_year\_month|reporting\_periods(site\_id, year, month)|
|UNIQUE (partial)|uq\_active\_submission|submissions(site\_id, form\_id, reporting\_period\_id) WHERE is\_deleted = false|
|UNIQUE|uq\_form\_version\_number|form\_versions(form\_id, version\_number)|
|UNIQUE|uq\_field\_version\_number|field\_versions(field\_id, version\_number)|
|UNIQUE|uq\_formula\_version\_number|formula\_versions(formula\_id, version\_number)|
|UNIQUE|uq\_vs\_version\_number|value\_set\_versions(value\_set\_id, version\_number)|
|UNIQUE|uq\_wf\_version\_number|workflow\_versions(workflow\_id, version\_number)|
|UNIQUE|uq\_wf\_level\_order|workflow\_levels(workflow\_version\_id, level\_number)|
|UNIQUE|uq\_submission\_value|submission\_values(submission\_id, field\_id)|
|UNIQUE|uq\_app\_config\_key|app\_config(config\_key)|
|UNIQUE|uq\_report\_template\_code|report\_templates(code)|

**CRITICAL: The partial unique constraint on submissions (WHERE is\_deleted = false) is the duplicate guard. Soft-deleted submissions do not block new ones for the same period.**

# **9. Indexes**

|**Type**|**Name**|**Definition**|
| :- | :- | :- |
|INDEX|idx\_access\_matrix\_user|access\_matrix(user\_id)|
|INDEX|idx\_access\_matrix\_scope|access\_matrix(scope\_type, scope\_site\_id)|
|INDEX|idx\_submissions\_period|submissions(reporting\_period\_id)|
|INDEX|idx\_submissions\_site\_form|submissions(site\_id, form\_id)|
|INDEX|idx\_submissions\_status|submissions(status)|
|INDEX|idx\_sub\_values\_submission|submission\_values(submission\_id)|
|INDEX|idx\_periods\_site\_status|reporting\_periods(site\_id, status)|
|INDEX|idx\_notifications\_user\_unread|notifications(user\_id) WHERE is\_read = false|
|INDEX|idx\_approval\_actions\_submission|approval\_actions(submission\_id)|
|INDEX|idx\_issues\_submission|issues(submission\_id)|
|INDEX|idx\_proof\_docs\_submission|proof\_documents(submission\_id)|
|INDEX|idx\_proof\_docs\_field|proof\_documents(field\_id) WHERE field\_id IS NOT NULL|
|INDEX|idx\_vsv\_status|value\_set\_versions(value\_set\_id, status)|
|INDEX|idx\_form\_versions\_form|form\_versions(form\_id)|
|INDEX|idx\_field\_versions\_field|field\_versions(field\_id)|
|DEFERRED|idx\_field\_config\_gin|GIN on field\_versions(field\_config) — defer to performance tuning|
|DEFERRED|idx\_formula\_tokens\_gin|GIN on formula\_versions(tokens) — defer to performance tuning|

# **10. Soft-Delete and Lifecycle Rules**
**Rule: No hard deletes anywhere in the system.**

|**[ ]**|Every table (except app\_config, notifications) has is\_deleted BOOLEAN NOT NULL DEFAULT false.|
| :-: | :- |
|**[ ]**|deleted\_at, deleted\_by, delete\_reason set on soft-delete. delete\_reason mandatory in service layer.|
|**[ ]**|All queries filter WHERE is\_deleted = false unless explicitly fetching deleted records.|
|**[ ]**|Approved submissions: is\_locked = true AND is\_deleted = false. Both checked on all write paths.|
|**[ ]**|Approved value\_set\_versions: immutable once status = Approved. No edits to entries or workflow cols.|
|**[ ]**|Version tables (form\_versions, field\_versions, formula\_versions, value\_set\_versions, workflow\_versions) get only created\_at/by — immutable once published/approved.|
|**[ ]**|No ON DELETE CASCADE FK. All deletes go through service layer.|
|**[ ]**|app\_config rows updated in place — no soft-delete.|
|**[ ]**|audit\_log DEFERRED. MVP substitute: lifecycle cols + formula\_inputs\_snapshot.|

# **11. Access Matrix Permission Model**
**The access\_matrix table is the ONLY source of truth.** All users are just users. Access comes exclusively from access\_matrix rows. No code checks any user field for permission decisions.

|**Rule**|**Detail**|
| :- | :- |
|**Permission fn**|get\_user\_permissions(user\_id, scope\_type, scope\_id, entity\_type) → dict of flag: bool. Cached per request.|
|**Decorator**|@require\_permission(entity, action, scope\_param=None) — wraps all protected routes. Returns 403 + no\_access.html on failure.|
|**Scope MVP**|global / site only. scope\_region\_id col reserved but always NULL.|
|**Scope validation**|scope\_type=global → both scope\_site\_id and scope\_region\_id must be NULL. scope\_type=site → scope\_site\_id must be set.|
|**No archetype checks**|users.archetype removed. No code reads archetype. Period.|
|**Last active user guard**|Service layer blocks deactivation of the last user holding a given critical permission (e.g. last user with can\_manage\_users globally).|
|**Self-approval**|submitted\_by must never equal actor\_id in approval\_actions. Enforced in APPROV service.|
|**11 flags**|can\_view / can\_create / can\_edit / can\_delete / can\_submit / can\_approve / can\_reject / can\_reopen / can\_export / can\_manage\_forms / can\_manage\_users|

# **12. Value Set Version Approval Workflow**
**Emission factors and constants directly affect GHG calculations. Only Approved value\_set\_versions may be used in published forms and formula evaluations.**

### **State Machine**

|**From**|**To**|**Condition / Actor**|
| :- | :- | :- |
|Draft|Submitted|User with required permission submits value set version for approval. submitted\_by + submitted\_at set.|
|Submitted|Approved|User with can\_approve permission approves. approved\_by + approved\_at set. Version becomes immutable. effective\_to on previous Approved version closed.|
|Submitted|Rejected|User with can\_approve permission rejects. rejected\_by + rejected\_at + rejection\_reason set. Mandatory reason required in service layer.|
|Rejected|Draft|User corrects entries and resets to Draft for resubmission. A new value\_set\_version row is created — do not mutate the Rejected row.|

|**[ ]**|Only value\_set\_versions with status = Approved may be referenced in published form field\_config (field\_type=dropdown) or used in formula evaluations.|
| :-: | :- |
|**[ ]**|Service layer enforces Approved-only rule at form publish time and at formula calculation time.|
|**[ ]**|Rejected → Draft creates a new version row. The Rejected row is never mutated.|
|**[ ]**|rejection\_reason is mandatory in service layer when status → Rejected (schema allows NULL but service rejects blank).|
|**[ ]**|Approver of a value\_set\_version must not be the same user who submitted it — same self-approval rule as submissions.|
|**[ ]**|value\_sets.current\_version\_id points to the current Approved version. Updated atomically when a new version is Approved.|

# **13. Monthly Reporting Period Model**
**Monthly standalone is MVP. Quarterly and annual are aggregated views over approved monthly data — NOT separate submission types.**

**India financial year:** April–March. FY start month stored in app\_config (key = financial\_year\_start\_month, default = 4).

|**Period Type**|**Status**|**Notes**|
| :- | :- | :- |
|Monthly|MVP|SPOC selects Year + Month. One submission per site + form + monthly period.|
|Quarterly|Deferred|View of approved Apr+May+Jun monthly data. Not a submission type.|
|Annual|Deferred|View of all approved monthly data for the FY. Not a submission type.|

### **Period Status Transitions**

|**From**|**To**|**Condition / Actor**|
| :- | :- | :- |
|OPEN|SUBMISSION\_CLOSED|User with required permission closes submission window.|
|SUBMISSION\_CLOSED|LOCKED|User with required permission locks the period.|
|LOCKED|REOPENED|User with can\_reopen permission. reopen\_reason mandatory. reopened\_at + reopened\_by set.|
|REOPENED|OPEN|Period re-enters editable state.|

# **14. Form Versioning Rules**

|**[ ]**|forms.current\_version\_id always points to the latest Published version.|
| :-: | :- |
|**[ ]**|New form\_version on every publish. Old version → Archived.|
|**[ ]**|version\_number monotonically increasing per form\_id. Never reused.|
|**[ ]**|Submissions locked to form\_version\_id at creation. Never auto-migrated.|
|**[ ]**|Published form\_version is immutable.|
|**[ ]**|Only one Published version per form — enforced in service layer.|
|**[ ]**|A form may only be published if all dropdown fields reference Approved value\_set\_versions.|

# **15. Field Versioning Rules**

|**[ ]**|field\_code is the stable identifier. Never changes across versions.|
| :-: | :- |
|**[ ]**|field\_name is display-only and may change between versions.|
|**[ ]**|Each field\_version bound to a specific form\_version\_id.|
|**[ ]**|field\_config JSONB holds all type-specific config. For file type: accepted\_mime\_types list in config.|
|**[ ]**|field\_type=file: raw\_value in submission\_values stores the proof\_document storage\_key.|
|**[ ]**|field\_type=table deferred to v2.|
|**[ ]**|Calculated fields in field\_config must reference a specific formula\_version\_id, not 'latest'.|

# **16. Formula Versioning Rules**

|**[ ]**|Formula evaluation: simpleeval on Flask only. Never eval() or exec().|
| :-: | :- |
|**[ ]**|Each formula\_version: immutable expression + tokens JSONB.|
|**[ ]**|formula\_version\_id snapshotted into submission\_values at submission time.|
|**[ ]**|formula\_inputs\_snapshot stores raw inputs — MVP audit substitute.|
|**[ ]**|Old approved submission\_values never silently recalculate.|
|**[ ]**|Browser-side preview (Vanilla JS) is preview only. Flask is authoritative.|
|**[ ]**|Formulas may only reference value\_set\_versions with status = Approved.|

# **17. Workflow Versioning Rules**

|**[ ]**|submissions.workflow\_version\_id locked at submission creation.|
| :-: | :- |
|**[ ]**|In-flight submissions follow the workflow\_version they started on.|
|**[ ]**|A new workflow\_version does not affect existing in-flight submissions.|
|**[ ]**|SEQUENTIAL mode: sequence\_number must be set for all approvers at that level.|
|**[ ]**|ANY\_ONE mode: sequence\_number must be NULL for all approvers at that level.|
|**[ ]**|submitted\_by must never equal actor\_id — enforced in APPROV service.|

# **18. Submission Status State Machine**
All other transitions return HTTP 409. APPROV service is the ONLY module that writes submissions.status.

|**From**|**To**|**Condition / Actor**|
| :- | :- | :- |
|(none)|Draft|SUBMIT creates submission. User with can\_submit. Period must be OPEN.|
|Draft|Submitted|SPOC submits. Duplicate guard fires. last\_status\_changed\_at set.|
|Submitted|Under\_Review|Level-1 approver opens. APPROV service.|
|Under\_Review|Changes\_Requested|Approver requests changes. Mandatory comment.|
|Under\_Review|Rejected|Approver rejects. Mandatory comment.|
|Under\_Review|Under\_Review|Multi-level: level approves, next level takes over. current\_level increments.|
|Under\_Review|Approved|Final level approves. approved\_by + approved\_at + is\_locked=true set atomically.|
|Changes\_Requested|Resubmitted|SPOC resubmits after addressing changes.|
|Resubmitted|Under\_Review|APPROV picks up at level 1.|

**When status → Approved: approved\_by, approved\_at, is\_locked=true, last\_status\_changed\_at all set in one atomic transaction. is\_locked is then checked on ALL write paths permanently.**

# **19. Open Questions — All Resolved**

|**#**|**Question**|**Decision**|**Status**|
| :- | :- | :- | :- |
|Q1|scope\_id FK design|Split into scope\_site\_id + scope\_region\_id. scope\_region\_id always NULL in MVP.|[x] Closed|
|Q2|FY start month config|app\_config table. Seed row: financial\_year\_start\_month = 4.|[x] Closed|
|Q3|approval\_mode schema|Schema allows all 4 values. UI exposes ANY\_ONE + SEQUENTIAL only in MVP.|[x] Closed|
|Q4|value\_set effective\_from|Admin-set; defaults to approval date if not specified.|[x] Closed|
|Q5|proof per-field vs per-submission|field\_id nullable on proof\_documents. Both supported.|[x] Closed|
|Q6|notification event\_type list|VARCHAR now. NOTIFY service defines constants.|[x] Closed|
|Q7|delete\_reason mandatory|Service raises 400 if blank. Schema allows NULL.|[x] Closed|
|Q8|value\_set entry deactivation|is\_active=false hides in UI. Historical submissions preserve entry\_code.|[x] Closed|
|Q9|GIN indexes timing|Deferred to performance tuning.|[x] Closed|
|Q10|notifications lifecycle|Minimal (created\_at only). No soft-delete.|[x] Closed|

# **20. Final Sign-Off Checklist**
**All items must be checked AND team lead must confirm on WhatsApp before Owner A writes any Alembic migration file.**

### **Schema Completeness**

|**[ ]**|All 26 MVP tables reviewed and agreed by all 3 owners.|
| :-: | :- |
|**[ ]**|regions confirmed as deferred. No region\_id on sites in MVP.|
|**[ ]**|All deferred tables confirmed as out of scope for MVP.|
|**[ ]**|All column types agreed.|
|**[ ]**|All FKs confirmed. ON DELETE RESTRICT as default.|

### **v3 Changes Confirmed**

|**[ ]**|users.archetype removed. users is identity/auth only. No code reads archetype for permissions.|
| :-: | :- |
|**[ ]**|sites.company\_name VARCHAR(255) NULL agreed and added.|
|**[ ]**|value\_set\_versions approval workflow agreed: Draft → Submitted → Approved / Rejected → Draft.|
|**[ ]**|Only Approved value\_set\_versions usable in published forms and calculations — enforced in service layer.|
|**[ ]**|field\_type=file added to enum. file type fields store proof\_document storage\_key in raw\_value.|
|**[ ]**|proof\_documents.field\_id confirmed nullable. Supports both field-level and submission-level proofs.|
|**[ ]**|All 'Super Admin only' references replaced with 'user with required permission'. Access governed by access\_matrix only.|

### **Constraints and Integrity**

|**[ ]**|Partial unique constraint on submissions WHERE is\_deleted=false confirmed.|
| :-: | :- |
|**[ ]**|UNIQUE(site\_id, year, month) on reporting\_periods confirmed.|
|**[ ]**|UNIQUE(form\_id, field\_code) on fields confirmed.|
|**[ ]**|uq\_app\_config\_key and uq\_report\_template\_code confirmed.|
|**[ ]**|All enum value lists agreed and complete.|

### **Access and Security**

|**[ ]**|11 permission flag columns on access\_matrix confirmed.|
| :-: | :- |
|**[ ]**|scope\_type = global / site only in MVP. scope\_region\_id col reserved but always NULL.|
|**[ ]**|Self-approval block confirmed — actor\_id != submitted\_by enforced in Flask.|
|**[ ]**|Same self-approval rule applied to value\_set\_version approval.|
|**[ ]**|No code reads users.archetype for any permission decision.|

### **Versioning and Immutability**

|**[ ]**|Submissions locked to form\_version\_id and workflow\_version\_id at creation.|
| :-: | :- |
|**[ ]**|Approved value\_set\_versions are immutable — entries cannot be added or changed after approval.|
|**[ ]**|formula\_inputs\_snapshot confirmed as MVP audit substitute.|
|**[ ]**|simpleeval only — never eval() or exec().|
|**[ ]**|is\_locked = true when submission Approved. Checked on ALL write paths.|

### **Open Questions**

|**[x]**|Q1–Q10 all resolved. No blocking questions remain.|
| :-: | :- |

### **Lead Sign-Off**

|**[ ]**|Lead has reviewed this v3 document in full.|
| :-: | :- |
|**[ ]**|Lead confirms: Phase 1 migration writing (001–012) may begin.|
|**[ ]**|Lead sign-off communicated on WhatsApp with date and time.|

**Once all boxes are ticked and WhatsApp confirmation received, Owner A may begin Alembic migrations 001–012.**
CONFIDENTIAL — INTERNAL USE ONLY  |  June 2026	Page 
