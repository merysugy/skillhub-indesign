# Phase 4b-4c - Proposals from captures

Two situations:
- **4b.** The user sends screenshots or mockups of a product and asks where
  and how they would go in the document.
- **4c.** The user sends a capture of a page area (usually empty space) and
  asks what could go there.

In both, use what you know of the document (its sections, its argument, its
identity) to propose, show the proposal in context, and wait, unless the user
also asked for the editable files.

## 4b. Where product screenshots go

1. **Understand each capture.** What screen it is, what it shows, which
   panels it has, its language, and whether it has real data.
2. **Match captures to sections.** A capture earns its place where it proves
   what the text says: the overview screen next to the section that
   presents the product, a detail panel next to the use case it illustrates,
   an action flow (alert, then task) next to the benefits.
3. **Decide the treatment** for each:
   - **Hero**: one full screen, once, in a neutral browser or device frame,
     with numbered callouts and a legend that ties each number to the text.
   - **Detail**: a crop of the relevant panel, as a thumbnail next to a text
     or inside a card.
   - **Sequence**: two or three crops with arrows (step 1, step 2).
   - Always with a caption. Captions and callout texts are yours: mark them.
4. **Advise against** the captures that do not help, with the reason:
   repeated content, wrong language, too dense to read at print size, real
   data, third-party imagery under licence (maps, stock), or a location or
   person that should not be published.
5. **Count the cost**: new pages, text that has to shrink to make room.

Deliver a PDF in the document's style:
- First page: a map table (capture thumbnail → where → how), including the
  captures not used and why.
- Then one page per change, as it would look, with a small tag on each one
  ("Proposal · new page between X and Y", "Proposal · page N with capture").
- List the data, licence and language checks the user must do before
  publishing.

## 4c. What to put in an empty area

1. **Measure the area**: width (a column? the full text width?) and free
   height. If the capture is from the user's InDesign, use the document's
   grid; the text above may grow, so leave room.
2. **Read the text next to it** and propose what illustrates it best: the
   section's own diagram adapted to that size, a box with the key idea, a
   key figure, a screenshot crop, a pull quote. Prefer reusing an element
   the document already has (same visual language) over a new one.
3. **Adapt, don't shrink.** A wide diagram placed in a column is
   recomposed (stacked, two by two, titles split into title and subtitle),
   not scaled down until the text is unreadable. Keep the document's text
   sizes.
4. **Show it in context** with `preview_model.py --page`, using the text the
   user sent, and say that InDesign may compose it slightly differently.
5. If the user asked for the editable file too, build the `.idms`
   (`04-idms-blocks.md`) and deliver both together: the proposal image and
   the block.
6. Point out problems you see in the capture (broken emphasis, empty
   paragraphs used as spacing, missing space between paragraphs, text or
   contacts from another document).

## Rendering the proposal pages

Same method as the layout proposal (`03-visual-resources.md`): HTML in the
document's style rendered to PDF, every page looked at before delivering.
For screenshots in a browser frame: a thin border, a top bar with three dots
and the screen's name, the image at full frame width. Callouts are small
numbered circles in the accent colour placed on the panels' corners so they
do not cover titles.
