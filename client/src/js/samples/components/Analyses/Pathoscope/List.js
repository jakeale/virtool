import React from "react";
import PropTypes from "prop-types";
import FlipMove from "react-flip-move"
import { Panel } from "react-bootstrap";
import { forIn, includes, sortBy, flatten } from "lodash";

import PathoscopeEntry from "./Entry";
import PathoscopeIsolate from "./Isolate";
import { Icon } from "../../../../base";

export default class PathoscopeList extends React.Component {

    static propTypes = {
        expanded: PropTypes.arrayOf(PropTypes.string),
        showReads: PropTypes.bool,
        toggleIn: PropTypes.func,
        data: PropTypes.arrayOf(PropTypes.object).isRequired
    };

    setScroll = (virusId, scrollLeft) => {
        forIn(this.refs, (ref, key) => {
            if (key.split("-")[0] === virusId) {
                ref.scrollTo(scrollLeft);
            }
        });
    };

    render () {

        if (this.props.data.length) {
            let rows = this.props.data.map((item, index) => {

                const expanded = includes(this.props.expanded, item.id);

                const components = [
                    <PathoscopeEntry
                        key={item.id}
                        {...item}
                        toggleIn={this.props.toggleIn}
                        showReads={this.props.showReads}
                        in={expanded}
                    />
                ];

                if (expanded) {
                    const isolateComponents = sortBy(item.isolates, "pi").reverse().map((isolate) => {
                        const key = `${item.id}-${isolate.id}`;

                        return <PathoscopeIsolate
                            ref={key}
                            key={key}
                            virusId={item._id}
                            maxDepth={item.maxDepth}
                            maxGenomeLength={item.maxGenomeLength}
                            {...isolate}
                            setScroll={this.setScroll}
                            showReads={this.props.showReads}
                        />
                    });

                    return components.concat(
                        <div key={index} className="list-group-item pathoscope-virus-detail spaced">
                            {isolateComponents}
                        </div>
                    );
                }

                return components;

            });

            return (
                <div>
                    <FlipMove
                        typeName="div"
                        className="list-group"
                        enterAnimation="accordionVertical"
                        leaveAnimation={false}
                    >
                        {flatten(rows)}
                    </FlipMove>
                </div>
            );
        }

        // Show a message if no hits matched the filters.
        return (
            <Panel className="text-center">
                <Icon name="info" /> No hits found.
            </Panel>
        );
    }

}
