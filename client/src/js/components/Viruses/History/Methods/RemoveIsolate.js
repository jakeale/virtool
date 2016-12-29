/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * @exports RemoveIsolateMethod
 */

'use strict';

import React from 'react';
import { Row, Col, Badge, Modal, InputGroup, Panel, PanelGroup } from 'react-bootstrap';
import { Icon } from "virtool/js/components/Base";
import { formatIsolateName } from 'virtool/js/utils';

var SequenceForm = require('virtool/js/components/Viruses/Manage/Detail/Sequences/Form');

/**
 * A modal component that details the removed isolate and all of it's sequences.
 *
 * @class
 */
var MethodDetailModal = React.createClass({

    propTypes: {
        show: React.PropTypes.bool,
        onHide: React.PropTypes.func.isRequired,
        isolate: React.PropTypes.object.isRequired,
        message: React.PropTypes.element.isRequired
    },

    render: function () {
        // Each sequence is described by a readonly form, BaseSequence.
        var sequenceComponents = this.props.isolate.sequences.map(function (document, index) {
            return (
                <Panel key={index} eventKey={index} header={document._id}>
                    <SequenceForm
                        sequenceId={document._id}
                        definition=""

                        host={document.host}
                        sequence={document.sequence}

                    />
                </Panel>
            );
        });

        return (
            <Modal show={this.props.show} onHide={this.props.onHide} animation={false}>
                <Modal.Header>
                    {this.props.message}
                </Modal.Header>
                <Modal.Body>
                    <Row>
                        <Col md={6}>
                            <InputGroup
                                type='text'
                                label='Source Type'
                                value={_.capitalize(this.props.isolate.source_type)}
                                readOnly
                            />
                        </Col>
                        <Col md={6}>
                            <InputGroup
                                type='text'
                                label='Source Name'
                                value={this.props.isolate.source_name}
                                readOnly
                            />
                        </Col>
                    </Row>
                    <h5>
                        <Icon name='dna' /> <strong>Sequences </strong>
                        <Badge>{sequenceComponents.length}</Badge>
                    </h5>
                    <PanelGroup defaultActiveKey={0} accordion>
                        {sequenceComponents}
                    </PanelGroup>
                </Modal.Body>
            </Modal>
        )
    }

});

/**
 * Renders a decription of a remove_isolate change.
 *
 * @class
 */
var RemoveIsolateMethod = React.createClass({

    getInitialState: function () {
        // State determines whether a modal detailing the change should be shown.
        return {show: false};
    },

    /**
     * Shows the detail modal. Triggered by clicking the question icon.
     *
     * @func
     */
    showModal: function () {
        this.setState({show: true});
    },

    /**
     * Hides the detail modal. Triggered as the modal onHide prop.
     *
     * @func
     */
    hideModal: function () {
        this.setState({show: false});
    },

    shouldComponentUpdate: function (nextProps, nextState) {
        // Only update if the modal is being toggled.
        return nextState.show !== this.state.show;
    },

    render: function () {
        // Get the part of the changes object that describes the change in the isolates.
        var fieldChange = _.find(this.props.changes, function (change) {
            return change[1] == 'isolates';
        });

        // Get the isolate from the change data.
        var isolate = fieldChange[2][0][1];

        // Parse out the isolate name from the isolate object.
        var isolateName = formatIsolateName(isolate);

        // Make a message describing the basics of the change which will be shown in the HistoryItem and the modal
        // title.
        var message = (
            <span>
                <Icon name='lab' bsStyle='danger' /> Removed isolate
                <em> {isolateName} ({isolate.isolate_id})</em>
            </span>
        );

        return (
            <span>
                <span>{message} </span>

                <Icon name='question' bsStyle='info' onClick={this.showModal} />

                <MethodDetailModal
                    show={this.state.show}
                    onHide={this.hideModal}
                    isolate={isolate}
                    message={message}
                />
            </span>
        );
    }

});

module.exports = RemoveIsolateMethod;