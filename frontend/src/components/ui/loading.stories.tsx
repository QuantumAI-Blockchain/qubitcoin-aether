import type { Meta, StoryObj } from "@storybook/react";
import { PhiSpinner, Skeleton } from "./loading";

/* =========================================================================
 * PhiSpinner stories
 * ========================================================================= */

const spinnerMeta: Meta<typeof PhiSpinner> = {
  title: "UI/PhiSpinner",
  component: PhiSpinner,
  tags: ["autodocs"],
  argTypes: {
    className: {
      control: "text",
      description: "Additional CSS classes (e.g., sizing)",
    },
  },
};

export default spinnerMeta;
type SpinnerStory = StoryObj<typeof PhiSpinner>;

/** Default phi-spiral loading spinner. */
export const Default: SpinnerStory = {
  args: {
    className: "",
  },
};

/** Large spinner for page-level loading. */
export const Large: SpinnerStory = {
  args: {
    className: "scale-200",
  },
  decorators: [
    (Story) => (
      <div className="flex h-40 w-40 items-center justify-center">
        <div className="flex items-center justify-center">
          <div className="phi-spin h-16 w-16 rounded-full border-2 border-quantum-violet/30 border-t-glow-cyan" />
        </div>
      </div>
    ),
  ],
};

/* =========================================================================
 * Skeleton stories (exported as named stories on the same file)
 * ========================================================================= */

export const SkeletonDefault: StoryObj<typeof Skeleton> = {
  name: "Skeleton / Default",
  render: () => (
    <div className="w-64 space-y-3">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  ),
};

export const SkeletonCard: StoryObj<typeof Skeleton> = {
  name: "Skeleton / Card Layout",
  render: () => (
    <div className="w-80 rounded-xl border border-border-subtle bg-bg-panel p-6">
      <Skeleton className="mb-4 h-6 w-32" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
      </div>
      <div className="mt-6 grid grid-cols-2 gap-4">
        <Skeleton className="h-16 w-full rounded-lg" />
        <Skeleton className="h-16 w-full rounded-lg" />
      </div>
    </div>
  ),
};

export const SkeletonStats: StoryObj<typeof Skeleton> = {
  name: "Skeleton / Stats Bar",
  render: () => (
    <div className="grid grid-cols-5 gap-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="panel-inset px-4 py-3 text-center">
          <Skeleton className="mx-auto mb-2 h-3 w-16" />
          <Skeleton className="mx-auto h-6 w-20" />
        </div>
      ))}
    </div>
  ),
};
