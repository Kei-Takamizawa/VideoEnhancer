import { expect, type Page } from "@playwright/test";

export async function assertPanelFits(page: Page) {
  const issues = await page.evaluate(() => {
    const problems: string[] = [];
    for (const node of document.querySelectorAll<HTMLElement>('[role="dialog"] button,[role="dialog"] label,[role="dialog"] dt,[role="dialog"] dd,[role="tooltip"]')) {
      const rect = node.getBoundingClientRect(), css = getComputedStyle(node);
      if (!rect.width || !rect.height || css.visibility === "hidden" || css.display === "none") continue;
      let top = rect.top, bottom = rect.bottom;
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent), bounds = parent.getBoundingClientRect();
        if (/auto|scroll|hidden/.test(style.overflowY)) { top = Math.max(top, bounds.top); bottom = Math.min(bottom, bounds.bottom); }
      }
      if (bottom <= top) continue;
      const name = node.textContent?.trim().slice(0, 90);
      if (rect.left < -1 || rect.right > innerWidth + 1 || top < -1 || bottom > innerHeight + 1) problems.push(`outside: ${name}`);
      if (node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1 && css.textOverflow !== "ellipsis") problems.push(`clipped: ${name} (${node.clientWidth}/${node.scrollWidth}, ${css.display})`);
    }
    return problems;
  });
  expect(issues).toEqual([]);
}
