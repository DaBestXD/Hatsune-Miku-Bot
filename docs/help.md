<!-- markdownlint-disable -->
• LayoutView
  │
  ├── TextDisplay
  │
  ├── Section
  │   ├── TextDisplay             (1–3)
  │   └── Accessory               (exactly one)
  │       ├── Button
  │       └── Thumbnail
  │
  ├── ActionRow
  │   ├── Button                  (up to 5)
  │   └── Select                  (occupies the row)
  │       ├── Select              (string options)
  │       ├── UserSelect
  │       ├── RoleSelect
  │       ├── MentionableSelect
  │       └── ChannelSelect
  │
  ├── MediaGallery
  │   └── MediaGalleryItem        (up to 10)
  │
  ├── File
  │
  ├── Separator
  │
  └── Container
      ├── TextDisplay
      │
      ├── Section
      │   ├── TextDisplay         (1–3)
      │   └── Accessory
      │       ├── Button
      │       └── Thumbnail
      │
      ├── ActionRow
      │   ├── Button
      │   └── Select
      │
      ├── MediaGallery
      │   └── MediaGalleryItem
      │
      ├── File
      │
      └── Separator

  Button, Select, and Thumbnail are not direct LayoutView children. A Container also cannot contain another Container.

• Modal
  │
  ├── TextDisplay                     (static Markdown text)
  │
  ├── Label                           (field title + optional description)
  │   │
  │   └── Component                   (exactly one)
  │       ├── TextInput
  │       │   ├── short
  │       │   └── paragraph
  │       │
  │       ├── Select
  │       │   ├── Select              (string options)
  │       │   ├── UserSelect
  │       │   ├── RoleSelect
  │       │   ├── MentionableSelect
  │       │   └── ChannelSelect
  │       │
  │       ├── FileUpload
  │       │
  │       ├── RadioGroup
  │       │   └── RadioGroupOption    (2–10 options)
  │       │
  │       ├── CheckboxGroup
  │       │   └── CheckboxGroupOption (1–10 options)
  │       │
  │       └── Checkbox                (single true/false value)
  │
  └── ActionRow                       (legacy/deprecated in modals)
      └── One input
          ├── TextInput
          └── Select
