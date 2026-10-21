import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HistoryRemoval } from "../src/HistoryRemoval";
import type { Job } from "../src/types";

describe("unreadable History removal", () => {
  it.each([false, true])("never selects hidden video choices (filesOnly=%s)", filesOnly => {
    const action = vi.fn();
    const job = { id: "a".repeat(32), unreadable_record: true } as Job;
    render(<HistoryRemoval jobs={[job]} filesOnly={filesOnly} action={action} close={() => {}} />);
    expect(screen.getByText("This record can't be read, so its videos stay where they are.")).toBeTruthy();
    expect(screen.queryByLabelText("Move the finished videos to the Recycle Bin")).toBeNull();
    expect(screen.queryByLabelText("Move the originals to the Recycle Bin")).toBeNull();
    if (filesOnly) {
      expect((screen.getByRole("button", { name: "Remove selected items" }) as HTMLButtonElement).disabled).toBe(true);
      fireEvent.click(screen.getByLabelText("Remove from History"));
    }
    fireEvent.click(screen.getByRole("button", { name: "Remove selected items" }));
    expect(action).toHaveBeenCalledWith(job, "remove", { ids: [job.id], history: true, output: false, original: false });
  });
});
