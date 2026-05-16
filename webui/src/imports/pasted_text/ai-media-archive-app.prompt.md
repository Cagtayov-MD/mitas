Create a professional dark-themed web application for an AI media archive system.

The app has two top-level workspace tabs:

1. MITAS Analysis Workstation
2. FaceBankBuilder

Use React, Tailwind, shadcn/ui, and lucide-react.
Use shadcn/ui Tabs for the top-level workspace switcher.
This is one application shell, but each tab must have a completely different layout and purpose.
Do not merge the two workflows into one crowded screen.

Global app shell:
- Dark professional broadcast-control-room aesthetic
- Top header with product name: MITAS AI Archive Suite
- Workspace tabs: “MITAS Analysis” and “FaceBankBuilder”
- Right side of header: GPU status, model status, storage status, user/review mode
- Style: serious media intelligence / archive workstation, not playful SaaS
- Dense but readable, optimized for desktop workstation screens

TAB 1: MITAS Analysis Workstation

Purpose:
MITAS analyzes long-form video/media files and produces timecoded AI evidence:
ASR transcript, speaker segments, face detections, OCR/credits, visual tags, logos, and metadata.
This workspace is for reviewing and correcting AI results from a media file.

Layout:
- Left/main: large video player
- Face bounding boxes over the video
- OCR/logo overlay toggle
- Current timecode visible
- Under video: current detected people chips and current tags
- Bottom: dense multi-layer timeline
- Right: review sidebar with internal tabs

Top media info row:
- Media title: “Belgesel Arşiv Kaydı - 1987”
- Archive ID: “TRT-1987-ANK-0042”
- Duration: 01:24:36
- Processing status: Analyzing / Review Needed / Approved
- Buttons: Upload Media, Start Analysis, Export, Review Queue

Timeline:
Create separate horizontal rows:
- ASR / Speech
- Speakers
- Faces
- OCR / Credits / KJ
- Visual Tags
- Logos
- Warnings / Low Confidence

Each event should have:
- time range
- confidence color
- clickable marker
- label
- warning state if low confidence

Timeline controls:
- zoom: 1m / 5m / 30m / full
- jump to next event
- jump to low confidence
- filter layers

Right review sidebar:
Use internal tabs:
- Transcript
- Faces
- Tags
- OCR/Credits
- Logos
- Metadata
- Evidence

Transcript tab:
- Turkish timecoded transcript lines
- active line highlighted
- editable speaker label
- buttons: confirm speaker, split segment, merge segment, mark uncertain

Faces tab:
- face thumbnails
- person candidate name
- confidence score
- unknown face groups: UNKNOWN_01, UNKNOWN_02
- buttons: approve person, reject, assign new person, add to face bank

Tags tab:
- accepted tags and suggested tags
- each tag has source, confidence, time range
- example tags: deniz, tekne, kalabalık, bayrak, camii, yangın, duman
- buttons: accept, reject, merge similar tags

OCR/Credits tab:
- raw OCR lines
- corrected OCR
- parsed role/person pairs
- fields: Director, Cast, Writer, Producer, Camera, Music
- buttons: accept, edit, reject, send to review

Logos tab:
- logo candidates
- example: TRT logo
- confidence
- screen position
- approve/reject

Metadata tab:
- media ID
- archive number
- title
- language
- source
- duration
- processing summary
- export status

Evidence tab:
- audit trail style
- source frame
- timecode
- model name
- confidence
- extracted text/tag/person
- decision reason

Review Queue:
Add visible queue cards for:
- Low confidence face match
- OCR conflict
- Unknown speaker
- Suspicious tag
- Logo candidate
Each card has Approve / Reject / Edit / Assign actions.

TAB 2: FaceBankBuilder

Purpose:
FaceBankBuilder prepares a clean face reference photo bank for MITAS.
It collects candidate photos for selected people, filters them, and lets the user approve or reject them before export.

Layout:
- Left sidebar: people list
- Main area: selected person's candidate photo grid
- Right side: metadata and review panel
- Bottom or top summary: build/export status

People list:
- search input
- filters: country, category, priority, status
- grouped people list
- each person shows:
  - display name
  - country
  - category
  - priority
  - candidate count
  - accepted count
  - warning badge if no good photo

Selected person header:
- display name
- person_id
- wikidata_qid
- category
- priority
- target: 8 accepted photos
- status: Need Review / Ready / Insufficient

Photo candidate grid:
Each photo card shows:
- image thumbnail
- source: Wikidata / Wikimedia Commons / Manual
- face score
- image resolution
- license badge
- status: raw, candidate_auto, accepted_by_user, rejected
- buttons:
  - accept
  - reject
  - wrong person
  - low quality
  - multi-face
  - open source

Right metadata panel:
Show details for selected photo:
- person_id
- display_name
- wikidata_qid
- source_url
- license
- author
- attribution
- face_bbox
- face_score
- image_width
- image_height
- rejection_reason

Review workflow:
- candidate_auto is not final
- accepted_by_user is final
- rejected_wrong_person
- rejected_no_face
- rejected_multi_face
- rejected_low_quality

Export section:
- Export accepted face bank for MITAS
- Show export path: E:\FaceBankBuilder\exports\mitas_face_seed
- Show validation status:
  - each person has at least 5 accepted photos
  - preferred target is 8-12 photos
  - warning if only one angle or low quality

Use realistic mock data:
People:
- Michael Jordan
- Recep Tayyip Erdoğan
- Barack Obama
- Lionel Messi
- Cristiano Ronaldo
- Mustafa Kemal Atatürk

FaceBankBuilder statuses:
- 8 candidates / 4 accepted / 2 rejected
- license missing warning
- multiple face warning
- no good photo warning

Visual style:
- Dark professional archive/data curation tool
- Compact tables, badges, cards, thumbnails
- Serious, not playful
- Cyan/blue accents
- Amber warnings
- Red rejected
- Green accepted

Technical:
- Use mock data arrays
- No backend
- No real file upload
- No real API calls
- Build it as a clean frontend prototype