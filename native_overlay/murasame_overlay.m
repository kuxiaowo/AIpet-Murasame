#import <Cocoa/Cocoa.h>
#import <CoreGraphics/CoreGraphics.h>
#import <fcntl.h>
#import <sys/file.h>
#import <unistd.h>

@interface MurasamePanel : NSPanel <NSTextViewDelegate>
@property(nonatomic, copy) NSString *imagePath;
@property(nonatomic, copy) NSString *textPath;
@property(nonatomic, copy) NSString *statePath;
@property(nonatomic, copy) NSString *visibilityPath;
@property(nonatomic, copy) NSString *commandPath;
@property(nonatomic, strong) NSTextField *textField;
@property(nonatomic, strong) NSTextView *inputView;
@property(nonatomic, copy) NSString *latestText;
@property(nonatomic, strong) NSDate *lastImageDate;
@property(nonatomic) BOOL fullscreen;
@property(nonatomic) BOOL qtVisible;
@property(nonatomic) BOOL shown;
@property(nonatomic) BOOL dragging;
@property(nonatomic) NSPoint dragOffset;
@property(nonatomic) BOOL inputMode;
@end

@implementation MurasamePanel
- (BOOL)canBecomeKeyWindow { return YES; }
- (BOOL)canBecomeMainWindow { return NO; }

- (void)mouseDown:(NSEvent *)event {
    if (!self.fullscreen) return;
    if (event.locationInWindow.y < self.frame.size.height * 0.38) {
        self.inputMode = YES;
        self.level = NSFloatingWindowLevel;
        self.inputView.hidden = NO;
        self.inputView.editable = YES;
        self.inputView.string = @"";
        [self makeKeyAndOrderFront:nil];
        [NSApp activateIgnoringOtherApps:YES];
        [self makeFirstResponder:self.inputView];
    }
}

- (void)otherMouseDown:(NSEvent *)event {
    if (!self.fullscreen) return;
    self.dragOffset = event.locationInWindow;
    self.dragging = YES;
}

- (void)otherMouseDragged:(NSEvent *)event {
    if (!self.dragging) return;
    NSPoint mouse = NSEvent.mouseLocation;
    [self setFrameOrigin:NSMakePoint(mouse.x - self.dragOffset.x,
                                     mouse.y - self.dragOffset.y)];
}

- (void)otherMouseUp:(NSEvent *)event { self.dragging = NO; }

- (BOOL)textView:(NSTextView *)textView
doCommandBySelector:(SEL)selector {
    if (textView != self.inputView) return NO;
    if (selector == @selector(insertNewline:)) {
        NSString *text = [textView.string
            stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
        if (text.length > 0) {
            [text writeToFile:self.commandPath atomically:YES
                      encoding:NSUTF8StringEncoding error:nil];
        }
        [self endInput];
        return YES;
    }
    if (selector == @selector(cancelOperation:)) {
        [self endInput];
        return YES;
    }
    return NO;
}

- (void)endInput {
    self.inputMode = NO;
    self.level = 101;
    self.inputView.editable = NO;
    self.inputView.hidden = YES;
    [self makeFirstResponder:nil];
}
@end

static BOOL frontmostAppHasFullscreenWindow(void) {
    NSRunningApplication *frontmost = NSWorkspace.sharedWorkspace.frontmostApplication;
    if (!frontmost || frontmost.processIdentifier == getpid()) return NO;
    NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
        kCGNullWindowID));
    NSRect screen = NSScreen.mainScreen.frame;
    for (NSDictionary *info in windows) {
        if ([info[(id)kCGWindowOwnerPID] intValue] != frontmost.processIdentifier) continue;
        CGRect rect;
        NSDictionary *bounds = info[(id)kCGWindowBounds];
        if (!CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)bounds, &rect)) continue;
        if (rect.size.width >= screen.size.width * 0.90 &&
            rect.size.height >= screen.size.height * 0.90) return YES;
    }
    return NO;
}

static void writeState(MurasamePanel *panel, BOOL fullscreen) {
    NSString *value = fullscreen ? @"1\n" : @"0\n";
    [value writeToFile:panel.statePath atomically:YES
              encoding:NSUTF8StringEncoding error:nil];
}

static void reloadQtVisibility(MurasamePanel *panel) {
    NSString *value = [NSString stringWithContentsOfFile:panel.visibilityPath
                                                 encoding:NSUTF8StringEncoding error:nil];
    if (value) {
        panel.qtVisible = value.integerValue != 0;
    }
}

static void reloadText(MurasamePanel *panel) {
    NSString *text = [NSString stringWithContentsOfFile:panel.textPath
                                                encoding:NSUTF8StringEncoding error:nil];
    if (text && ![text isEqualToString:panel.latestText]) {
        panel.latestText = text;
        if (!panel.inputMode) panel.textField.stringValue = text;
    }
}

static void reloadImage(MurasamePanel *panel, NSImageView *imageView) {
    NSDictionary *attributes = [[NSFileManager defaultManager]
        attributesOfItemAtPath:panel.imagePath error:nil];
    NSDate *modified = attributes[NSFileModificationDate];
    if (!modified || (panel.lastImageDate &&
                      [modified compare:panel.lastImageDate] != NSOrderedDescending)) return;
    NSImage *image = [[NSImage alloc] initWithContentsOfFile:panel.imagePath];
    if (image) {
        imageView.image = image;
        panel.lastImageDate = modified;
    }
}

static void tick(MurasamePanel *panel, NSImageView *imageView) {
    reloadQtVisibility(panel);
    reloadText(panel);
    reloadImage(panel, imageView);
    NSRunningApplication *frontmost = NSWorkspace.sharedWorkspace.frontmostApplication;
    BOOL fullscreen = frontmost.processIdentifier == getpid()
        ? panel.fullscreen : frontmostAppHasFullscreenWindow();
    if (fullscreen != panel.fullscreen) {
        panel.fullscreen = fullscreen;
        writeState(panel, fullscreen);
    }
    BOOL shouldShow = panel.fullscreen && !panel.qtVisible;
    if (shouldShow == panel.shown) return;
    panel.shown = shouldShow;
    if (shouldShow) [panel orderFrontRegardless]; else [panel orderOut:nil];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc < 6) return 2;
        NSString *imagePath = [NSString stringWithUTF8String:argv[1]];
        NSString *textPath = [NSString stringWithUTF8String:argv[2]];
        NSString *statePath = [NSString stringWithUTF8String:argv[3]];
        NSString *visibilityPath = [NSString stringWithUTF8String:argv[4]];
        NSString *commandPath = [NSString stringWithUTF8String:argv[5]];
        int lockFD = open(".native_overlay.lock", O_CREAT | O_RDWR, 0600);
        if (lockFD < 0 || flock(lockFD, LOCK_EX | LOCK_NB) != 0) return 0;

        NSImage *image = [[NSImage alloc] initWithContentsOfFile:imagePath];
        if (!image) return 1;
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];

        NSRect screen = NSScreen.mainScreen.visibleFrame;
        CGFloat scale = MIN(1.0, screen.size.height / MAX(image.size.height, 1));
        NSSize size = NSMakeSize(image.size.width * scale, image.size.height * scale);
        NSRect frame = NSMakeRect(NSMaxX(screen) - size.width - 24,
                                  NSMinY(screen) + 20, size.width, size.height);
        MurasamePanel *panel = [[MurasamePanel alloc]
            initWithContentRect:frame styleMask:NSWindowStyleMaskBorderless
            backing:NSBackingStoreBuffered defer:NO];
        panel.imagePath = imagePath;
        panel.textPath = textPath;
        panel.statePath = statePath;
        panel.visibilityPath = visibilityPath;
        panel.commandPath = commandPath;
        panel.opaque = NO;
        panel.backgroundColor = NSColor.clearColor;
        panel.hasShadow = NO;
        panel.hidesOnDeactivate = NO;
        panel.becomesKeyOnlyIfNeeded = NO;
        panel.floatingPanel = YES;
        panel.level = 101;
        panel.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorCanJoinAllApplications |
            NSWindowCollectionBehaviorFullScreenAuxiliary |
            NSWindowCollectionBehaviorStationary;

        NSView *root = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, size.width, size.height)];
        NSImageView *imageView = [[NSImageView alloc] initWithFrame:root.bounds];
        imageView.image = image;
        imageView.imageScaling = NSImageScaleProportionallyUpOrDown;
        [root addSubview:imageView];

        NSRect textFrame = NSMakeRect(18, size.height * 0.42, size.width - 36, size.height * 0.28);
        NSTextField *textField = [[NSTextField alloc] initWithFrame:textFrame];
        textField.bezeled = NO;
        textField.drawsBackground = NO;
        textField.textColor = NSColor.whiteColor;
        textField.font = [NSFont systemFontOfSize:14 weight:NSFontWeightMedium];
        textField.editable = NO;
        textField.selectable = NO;
        textField.maximumNumberOfLines = 0;
        textField.lineBreakMode = NSLineBreakByWordWrapping;
        [root addSubview:textField];
        panel.textField = textField;

        NSTextView *inputView = [[NSTextView alloc] initWithFrame:textFrame];
        inputView.editable = NO;
        inputView.richText = NO;
        inputView.drawsBackground = NO;
        inputView.backgroundColor = NSColor.clearColor;
        inputView.textColor = NSColor.whiteColor;
        inputView.font = textField.font;
        inputView.delegate = panel;
        inputView.hidden = YES;
        [root addSubview:inputView];
        panel.inputView = inputView;
        panel.contentView = root;

        writeState(panel, NO);
        [NSTimer scheduledTimerWithTimeInterval:0.10 repeats:YES block:^(__unused NSTimer *timer) {
            tick(panel, imageView);
        }];
        [NSApp run];
    }
    return 0;
}
