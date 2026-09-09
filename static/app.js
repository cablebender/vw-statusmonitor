let latestStatus = null;
let latestHistory = null;


/*
 * Status laden
 */

async function loadStatus() {
    try {
        const response = await fetch(
            '/api/status',
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        latestStatus =
            await response.json();

        renderDashboard();
        renderTopology();

    } catch (error) {
        document.getElementById(
            'last-update'
        ).textContent =
            'Status konnte nicht geladen werden';

        console.error(
            'Status request failed:',
            error
        );
    }
}


/*
 * History laden
 */

async function loadHistory() {
    try {
        const response = await fetch(
            '/api/history',
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        latestHistory =
            await response.json();

        if (
            latestHistory.enabled
            && latestHistory.hours
        ) {
            document.getElementById(
                'history-info'
            ).textContent =
                'Historie: letzte '
                + latestHistory.hours
                + ' Stunden';
        }

        renderDashboard();

    } catch (error) {
        console.error(
            'History request failed:',
            error
        );
    }
}


/*
 * Statusliste
 */

function renderDashboard() {
    if (!latestStatus) {
        return;
    }

    const container =
        document.getElementById(
            'systems'
        );

    container.innerHTML = '';

    for (
        const check
        of latestStatus.checks
    ) {
        container.appendChild(
            createSystemCard(
                check
            )
        );
    }

    updatePageInformation();
}


function createSystemCard(check) {
    const status =
        normalizeStatus(
            check.status
        );

    const card =
        document.createElement(
            'article'
        );

    card.className =
        `system ${status}`;


    const top =
        document.createElement(
            'div'
        );

    top.className =
        'system-top';


    const name =
        document.createElement(
            'div'
        );

    name.className =
        'name';

    name.textContent =
        check.name;


    const description =
        document.createElement(
            'div'
        );

    description.className =
        'description';

    description.textContent =
        check.description || '';


    const details =
        document.createElement(
            'div'
        );

    details.className =
        'details';

    details.textContent =
        buildDetails(
            check
        );


    const state =
        document.createElement(
            'div'
        );

    state.className =
        'state';

    state.textContent =
        status.toUpperCase();


    top.appendChild(
        name
    );

    top.appendChild(
        description
    );

    top.appendChild(
        details
    );

    top.appendChild(
        state
    );


    card.appendChild(
        top
    );

    card.appendChild(
        createTimeline(
            check.name
        )
    );

    return card;
}


function buildDetails(check) {
    const details = [];

    if (
        check.http_status
        !== undefined
    ) {
        details.push(
            `HTTP ${check.http_status}`
        );
    }

    if (
        check.response_ms
        !== undefined
    ) {
        details.push(
            `${check.response_ms} ms`
        );
    }

    if (
        check.port
        !== undefined
    ) {
        details.push(
            `Port ${check.port}`
        );
    }

    if (check.error) {
        details.push(
            check.error
        );
    }

    return details.join(
        ' | '
    );
}


/*
 * Timeline
 */

function createTimeline(checkName) {
    const wrapper =
        document.createElement(
            'div'
        );

    wrapper.className =
        'timeline-wrapper';


    const timeline =
        document.createElement(
            'div'
        );

    timeline.className =
        'timeline';


    if (
        !latestHistory
        || !latestHistory.enabled
        || !latestHistory.from
        || !latestHistory.to
    ) {
        const segment =
            document.createElement(
                'div'
            );

        segment.className =
            'timeline-segment unknown';

        segment.style.left =
            '0%';

        segment.style.width =
            '100%';

        timeline.appendChild(
            segment
        );

        wrapper.appendChild(
            timeline
        );

        return wrapper;
    }


    const windowStart =
        new Date(
            latestHistory.from
        ).getTime();

    const windowEnd =
        new Date(
            latestHistory.to
        ).getTime();

    const windowLength =
        windowEnd - windowStart;


    const intervals =
        (
            latestHistory.checks
            && latestHistory.checks[
                checkName
            ]
        )
        || [];


    for (
        const interval
        of intervals
    ) {
        const intervalStart =
            new Date(
                interval.from
            ).getTime();

        const intervalEnd =
            new Date(
                interval.to
            ).getTime();

        const left =
            (
                (
                    intervalStart
                    - windowStart
                )
                / windowLength
            ) * 100;

        const width =
            (
                (
                    intervalEnd
                    - intervalStart
                )
                / windowLength
            ) * 100;


        const segment =
            document.createElement(
                'div'
            );

        const status =
            normalizeStatus(
                interval.status
            );

        segment.className =
            `timeline-segment ${status}`;

        segment.style.left =
            `${Math.max(
                0,
                left
            )}%`;

        segment.style.width =
            `${Math.max(
                0,
                width
            )}%`;


        if (
            status !== 'up'
            && width < 0.2
        ) {
            segment.classList.add(
                'timeline-small-event'
            );
        }


        segment.title =
            buildTimelineTooltip(
                interval
            );

        timeline.appendChild(
            segment
        );
    }


    const labels =
        document.createElement(
            'div'
        );

    labels.className =
        'timeline-labels';


    const fromLabel =
        document.createElement(
            'span'
        );

    fromLabel.textContent =
        `${latestHistory.hours}h`;


    const nowLabel =
        document.createElement(
            'span'
        );

    nowLabel.textContent =
        'jetzt';


    labels.appendChild(
        fromLabel
    );

    labels.appendChild(
        nowLabel
    );


    wrapper.appendChild(
        timeline
    );

    wrapper.appendChild(
        labels
    );

    return wrapper;
}


function buildTimelineTooltip(
    interval
) {
    const from =
        new Date(
            interval.from
        );

    const to =
        new Date(
            interval.to
        );

    return (
        interval.status.toUpperCase()
        + '\n'
        + from.toLocaleString()
        + ' - '
        + to.toLocaleString()
    );
}


/*
 * Topologie
 */

function renderTopology() {
    if (!latestStatus) {
        return;
    }

    const container =
        document.getElementById(
            'topology-container'
        );

    container.innerHTML = '';


    const checks =
        latestStatus.checks || [];


    if (checks.length === 0) {
        container.innerHTML =
            '<div class="loading-message">'
            + 'Keine Checks definiert.'
            + '</div>';

        return;
    }


    const graph =
        buildTopologyGraph(
            checks
        );


    const canvas =
        document.createElement(
            'div'
        );

    canvas.className =
        'topology-canvas';


    const nodeLayer =
        document.createElement(
            'div'
        );

    nodeLayer.className =
        'topology-node-layer';


    for (
        const level
        of graph.levels
    ) {
        const row =
            document.createElement(
                'div'
            );

        row.className =
            'topology-level';


        for (
            const check
            of level
        ) {
            row.appendChild(
                createTopologyNode(
                    check
                )
            );
        }

        nodeLayer.appendChild(
            row
        );
    }


    const svg =
        document.createElementNS(
            'http://www.w3.org/2000/svg',
            'svg'
        );

    svg.classList.add(
        'topology-lines'
    );


    canvas.appendChild(
        svg
    );

    canvas.appendChild(
        nodeLayer
    );

    container.appendChild(
        canvas
    );


    requestAnimationFrame(
        () => drawTopologyLines(
            canvas,
            svg,
            graph.edges
        )
    );
}


function buildTopologyGraph(checks) {
    const byName =
        new Map();

    for (
        const check
        of checks
    ) {
        byName.set(
            check.name,
            check
        );
    }


    const levelCache =
        new Map();


    function calculateLevel(
        name,
        visiting = new Set()
    ) {
        if (
            levelCache.has(
                name
            )
        ) {
            return levelCache.get(
                name
            );
        }


        if (
            visiting.has(
                name
            )
        ) {
            /*
             * Zirkuläre Abhängigkeit:
             * Darstellung trotzdem ermöglichen.
             */
            return 0;
        }


        const check =
            byName.get(
                name
            );

        if (!check) {
            return 0;
        }


        const dependencies =
            check.depends_on || [];


        if (
            dependencies.length === 0
        ) {
            levelCache.set(
                name,
                0
            );

            return 0;
        }


        const nextVisiting =
            new Set(
                visiting
            );

        nextVisiting.add(
            name
        );


        let highestParentLevel =
            0;


        for (
            const dependency
            of dependencies
        ) {
            highestParentLevel =
                Math.max(
                    highestParentLevel,
                    calculateLevel(
                        dependency,
                        nextVisiting
                    )
                );
        }


        const level =
            highestParentLevel + 1;


        levelCache.set(
            name,
            level
        );

        return level;
    }


    let highestLevel = 0;


    for (
        const check
        of checks
    ) {
        highestLevel =
            Math.max(
                highestLevel,
                calculateLevel(
                    check.name
                )
            );
    }


    const levels =
        Array.from(
            {
                length:
                    highestLevel + 1
            },
            () => []
        );


    for (
        const check
        of checks
    ) {
        const level =
            calculateLevel(
                check.name
            );

        levels[
            level
        ].push(
            check
        );
    }


    const edges = [];


    for (
        const check
        of checks
    ) {
        for (
            const dependency
            of (
                check.depends_on
                || []
            )
        ) {
            edges.push({
                from: dependency,
                to: check.name
            });
        }
    }


    return {
        levels,
        edges
    };
}


function createTopologyNode(
    check
) {
    const status =
        normalizeStatus(
            check.status
        );


    const node =
        document.createElement(
            'div'
        );

    node.className =
        `topology-node ${status}`;

    node.dataset.name =
        check.name;


    const name =
        document.createElement(
            'div'
        );

    name.className =
        'topology-node-name';

    name.textContent =
        check.name;


    const state =
        document.createElement(
            'div'
        );

    state.className =
        'topology-node-state';

    state.textContent =
        status.toUpperCase();


    node.appendChild(
        name
    );

    node.appendChild(
        state
    );


    if (check.description) {
        node.title =
            check.description;
    }


    return node;
}


function drawTopologyLines(
    canvas,
    svg,
    edges
) {
    svg.innerHTML = '';


    const canvasRect =
        canvas.getBoundingClientRect();


    svg.setAttribute(
        'width',
        canvas.scrollWidth
    );

    svg.setAttribute(
        'height',
        canvas.scrollHeight
    );

    svg.setAttribute(
        'viewBox',
        `0 0 ${canvas.scrollWidth} ${canvas.scrollHeight}`
    );


    for (
        const edge
        of edges
    ) {
        const fromNode =
            findTopologyNode(
                canvas,
                edge.from
            );

        const toNode =
            findTopologyNode(
                canvas,
                edge.to
            );


        if (
            !fromNode
            || !toNode
        ) {
            continue;
        }


        const fromRect =
            fromNode.getBoundingClientRect();

        const toRect =
            toNode.getBoundingClientRect();


        const startX =
            fromRect.left
            - canvasRect.left
            + canvas.scrollLeft
            + fromRect.width / 2;

        const startY =
            fromRect.bottom
            - canvasRect.top
            + canvas.scrollTop;


        const endX =
            toRect.left
            - canvasRect.left
            + canvas.scrollLeft
            + toRect.width / 2;

        const endY =
            toRect.top
            - canvasRect.top
            + canvas.scrollTop;


        const middleY =
            (
                startY
                + endY
            ) / 2;


        const path =
            document.createElementNS(
                'http://www.w3.org/2000/svg',
                'path'
            );


        path.setAttribute(
            'd',
            [
                `M ${startX} ${startY}`,
                `L ${startX} ${middleY}`,
                `L ${endX} ${middleY}`,
                `L ${endX} ${endY}`
            ].join(' ')
        );


        path.setAttribute(
            'class',
            'topology-edge'
        );


        svg.appendChild(
            path
        );
    }
}


function findTopologyNode(
    canvas,
    name
) {
    const nodes =
        canvas.querySelectorAll(
            '.topology-node'
        );

    for (
        const node
        of nodes
    ) {
        if (
            node.dataset.name
            === name
        ) {
            return node;
        }
    }

    return null;
}


/*
 * Allgemeine Informationen
 */

function updatePageInformation() {
    const lastUpdate =
        document.getElementById(
            'last-update'
        );

    const footerStatus =
        document.getElementById(
            'footer-status'
        );


    if (
        latestStatus
        && latestStatus.generated
    ) {
        const date =
            new Date(
                latestStatus.generated
            );

        lastUpdate.textContent =
            'Letzte Prüfung: '
            + date.toLocaleString();
    } else {
        lastUpdate.textContent =
            'Noch keine Prüfung durchgeführt';
    }


    const checks =
        latestStatus?.checks
        || [];


    const down =
        checks.filter(
            check =>
                check.status
                === 'down'
        ).length;


    const unknown =
        checks.filter(
            check =>
                check.status
                === 'unknown'
        ).length;


    if (down > 0) {
        footerStatus.textContent =
            `${down} System(e) DOWN`;
    } else if (unknown > 0) {
        footerStatus.textContent =
            `${unknown} System(e) UNKNOWN`;
    } else {
        footerStatus.textContent =
            'Alle Systeme UP';
    }
}


function normalizeStatus(status) {
    if (
        status === 'up'
        || status === 'down'
        || status === 'unknown'
    ) {
        return status;
    }

    return 'unknown';
}


/*
 * Nach Resize Linien neu zeichnen.
 */

let resizeTimer = null;

window.addEventListener(
    'resize',
    () => {
        clearTimeout(
            resizeTimer
        );

        resizeTimer =
            setTimeout(
                renderTopology,
                150
            );
    }
);


/*
 * Start
 */

loadStatus();
loadHistory();


setInterval(
    loadStatus,
    5000
);


setInterval(
    loadHistory,
    30000
);
